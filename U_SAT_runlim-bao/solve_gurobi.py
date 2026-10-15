import csv
import os
import time
from pathlib import Path

import gurobipy as gp
from gurobipy import GRB


def load_env_file():
    env_file = Path(__file__).with_name(".env")
    if not env_file.is_file():
        return

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_env_file()

required_license_settings = ("WLSACCESSID", "WLSSECRET", "LICENSEID")
missing_license_settings = [
    name for name in required_license_settings if not os.environ.get(name)
]
if missing_license_settings:
    raise RuntimeError(
        "Missing Gurobi license settings in .env: "
        + ", ".join(missing_license_settings)
    )

env = gp.Env(empty=True)
env.setParam("WLSACCESSID", os.environ["WLSACCESSID"])
env.setParam("WLSSECRET", os.environ["WLSSECRET"])
env.setParam("LICENSEID", int(os.environ["LICENSEID"]))
env.start()


def create_assignment_model(n, m, c, Ex_times):
    model = gp.Model("assignment", env=env)
    X = [[model.addVar(vtype=GRB.BINARY, name=f"X_{i}_{j}") for j in range(m)] for i in range(n)]
    O = [[model.addVar(vtype=GRB.BINARY, name=f"O_{i}_{j}") for j in range(m)] for i in range(n)]
    S = [[model.addVar(vtype=GRB.BINARY, name=f"S_{i}_{t}") for t in range(c)] for i in range(n)]
    Wmax = model.addVar(vtype=GRB.INTEGER, name="Wmax")
    model.update()
    return model, X, S, Wmax, O


def add_assignment_constraints(
    n, m, c, model, X, S, O, Wmax, task_power, Ex_times, precedence_relations
):
    cons = 0

    # (1) Objective
    model.setObjective(Wmax, GRB.MINIMIZE)

    # (2) Each task assigned to exactly one station
    for j in range(n):
        model.addConstr(
            gp.quicksum(X[j][k] for k in range(m))
            + gp.quicksum(O[j][k] for k in range(m))
            == 1
        )
        cons += 1

    # (3) Processing times at each station <= c
    for k in range(m):
        model.addConstr(
            gp.quicksum(Ex_times[j] * X[j][k] for j in range(n))
            + gp.quicksum(Ex_times[j] * O[j][k] for j in range(n))
            <= c
        )
        cons += 1

    # (4) Precedence: X[j,k] <= sum_{h<=k} X[i,h]
    for i, j in precedence_relations:
        for k in range(m):
            model.addConstr(
                X[j - 1][k] <= gp.quicksum(X[i - 1][h] for h in range(k + 1))
            )
            model.addConstr(
                O[j - 1][k] <= gp.quicksum(O[i - 1][h] for h in range(k + 1, m))
            )
            cons += 2
        model.addConstr(
            gp.quicksum(O[i - 1][k] for k in range(m))
            <= gp.quicksum(O[j - 1][k] for k in range(m))
        )
        cons += 1

    # (5) Each task assigned to exactly one start time
    for j in range(n):
        model.addConstr(
            gp.quicksum(S[j][t] for t in range(c - Ex_times[j] + 1)) == 1
        )
        cons += 1

    # (6) Precedence and start times
    for i, j in precedence_relations:
        if i > 0 and j > 0:
            for k in range(m):
                for t in range(c - Ex_times[j - 1] + 1):
                    tau_range = range(t - Ex_times[i - 1] + 1)
                    model.addConstr(
                        S[j - 1][t]
                        <= gp.quicksum(S[i - 1][tau] for tau in tau_range)
                        + 2
                        - X[i - 1][k]
                        - X[j - 1][k]
                        - O[i - 1][k]
                        - O[j - 1][k]
                    )
                    cons += 1

    # (7) Tasks sharing a station cannot overlap
    for i in range(n - 1):
        for j in range(i + 1, n):
            for k in range(m):
                for t in range(c):
                    model.addConstr(
                        X[i][k]
                        + X[j][k]
                        + O[i][k]
                        + O[j][k]
                        + gp.quicksum(
                            S[i][tau] for tau in range(t - Ex_times[i] + 1, t + 1)
                        )
                        + gp.quicksum(
                            S[j][tau] for tau in range(t - Ex_times[j] + 1, t + 1)
                        )
                        <= 3
                    )
                    cons += 1

    # (8) Power peak constraint
    for t in range(c):
        model.addConstr(
            gp.quicksum(
                task_power[j]
                * gp.quicksum(
                    S[j][s] for s in range(t - Ex_times[j] + 1, t + 1)
                )
                for j in range(n)
            )
            <= Wmax
        )
        cons += 1

    return model, cons


def solve_assignment_problem(n, m, c, Ex_times, precedence_relations, W):
    model, X, S, Wmax, O = create_assignment_model(n, m, c, Ex_times)
    model, cons = add_assignment_constraints(
        n, m, c, model, X, S, O, Wmax, W, Ex_times, precedence_relations
    )
    model.Params.TimeLimit = 3600

    try:
        model.optimize()
    except gp.GurobiError:
        return None, n * m + n * c, cons

    if model.SolCount == 0:
        return None, n * m + n * c, cons
    return model, n * m + n * c, cons


def input_file(file_name):
    W = []
    precedence_relations = set()
    Ex_Time = []

    with open(f"task_power/{file_name}.txt") as f:
        for line in f:
            W.append(int(line.strip()))

    with open(f"data/{file_name}.IN2") as f:
        lines = f.readlines()

    n = int(lines[0])
    for idx, line in enumerate(lines[1:], start=1):
        line = line.strip()
        if idx > n:
            pair = tuple(map(int, line.split(",")))
            if pair == (-1, -1):
                break
            precedence_relations.add(pair)
        else:
            Ex_Time.append(int(line))

    return n, W, precedence_relations, Ex_Time


def get_value(solution, n, m, c, W, Ex_times):
    X_values = [[0 for _ in range(m)] for _ in range(n)]
    O_values = [[0 for _ in range(m)] for _ in range(n)]
    S_values = [[0 for _ in range(c)] for _ in range(n)]

    for i in range(n):
        for k in range(m):
            X_values[i][k] = solution.getVarByName(f"X_{i}_{k}").X
            O_values[i][k] = solution.getVarByName(f"O_{i}_{k}").X

    for i in range(n):
        for t in range(c):
            S_values[i][t] = solution.getVarByName(f"S_{i}_{t}").X

    schedule = [[0 for _ in range(c)] for _ in range(m + 1)]

    for k in range(m):
        for j in range(n):
            for t in range(c):
                for t0 in range(Ex_times[j]):
                    if (
                        (X_values[j][k] == 1 or O_values[j][k] == 1)
                        and S_values[j][t - t0] == 1
                    ):
                        schedule[k][t] = W[j]

    schedule[m] = [sum(schedule[j][t] for j in range(m)) for t in range(c)]
    peak = max(schedule[m])
    return schedule, solution.getVarByName("Wmax").X, peak


def write_to_csv(result):
    with open("Output/result_gurobi.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(result)


def optimal(filename):
    n, W, precedence_relations, Ex_times = input_file(filename[0])
    m = filename[1]
    c = filename[2]
    print(f"n={n}, m={m}, c={c}")
    start_time = time.time()
    solution, var, cons = solve_assignment_problem(
        n, m, c, Ex_times, precedence_relations, W
    )
    end_time = time.time()
    print("Time taken:", end_time - start_time)
    if solution and end_time - start_time < 3600:
        print(f"Solution for {filename[0]} with n={n}, m={m}, c={c}:")
        schedule, Wmax, peak = get_value(solution, n, m, c, W, Ex_times)
        print("Peak =", Wmax)
        write_to_csv(
            [filename[0], n, m, c, Wmax, var, cons, end_time - start_time]
        )
    else:
        print("No solution found.")
        write_to_csv(
            [filename[0], n, m, c, "Timeout", var, cons, end_time - start_time]
        )


file_name = [
    ["MERTENS", 6, 6],
    ["MERTENS", 2, 18],
    ["BOWMAN", 5, 20],
    ["JAESCHKE", 8, 6],
    ["JAESCHKE", 3, 18],
    ["JACKSON", 8, 7],
    ["JACKSON", 3, 21],
    ["MANSOOR", 4, 48],
    ["MANSOOR", 2, 94],
    ["MITCHELL", 8, 14],
    ["MITCHELL", 3, 39],
    ["ROSZIEG", 10, 14],
    ["ROSZIEG", 4, 32],
    ["BUXEY", 7, 47],
    ["BUXEY", 14, 25],
    ["SAWYER", 14, 25],
    ["SAWYER", 7, 47],
]


for instance in file_name:
    optimal(instance)