import docplex.cp
from docplex.cp.model import CpoModel
import time
import csv
from pathlib import Path
from docplex.cp.config import context

context.solver.local.execfile = r"C:\Users\TRUONG GIANG\AppData\Local\Programs\Python\Python38\Scripts\cpoptimizer.exe"


def create_assignment_model(n, m, c, model, Ex_times):
    X = [[model.binary_var(name=f'X_{i}_{j}') for j in range(m)] for i in range(n)]
    O = [[model.binary_var(name=f'O_{i}_{j}') for j in range(m)] for i in range(n)]
    S = [[model.binary_var(name=f'S_{i}_{t}') for t in range(c)] for i in range(n)]
    Wmax = model.integer_var(name="Wmax")
    return model, X, S, Wmax, O

def add_assignment_constraints(n, m, c, model, X, S, O, Wmax, W, Ex_times, precedence_relations):
    cons = 0
    # (1) Objective
    model.add_constraint(model.minimize(Wmax))
    cons += 1
    # (2) Each task assigned to exactly one station
    for j in range(n):
        model.add_constraint(model.sum([X[j][k] for k in range(m)]) + model.sum([O[j][k] for k in range(m)]) == 1)
        cons += 1
        # print(" + ".join([f"X[{j},{k}]" for k in range(m)]) + " = 1")

    # (3) Processing times at each station ≤ c
    for k in range(m):
        model.add_constraint(model.sum([Ex_times[j] * X[j][k] for j in range(n)]) 
                             + model.sum([Ex_times[j] * O[j][k] for j in range(n)]) <= c)
        cons += 1
        # print(" + ".join([f"{Ex_times[j]}*X[{j},{k}]" for j in range(n)]) + f" <= {c}")
    
    # (4) Precedence: X[j,k] ≤ sum_{h<k} X[i,h] for i ≺ j
    for (i, j) in precedence_relations:
        for k in range(m):
            model.add_constraint(X[j-1][k] <= model.sum([X[i-1][h] for h in range(k + 1)]))
            model.add_constraint(O[j-1][k] <= model.sum([O[i-1][h] for h in range(k + 1, m)]))
            cons += 2
        model.add_constraint(model.sum([O[i-1][k] for k in range(m)]) <= model.sum([O[j-1][k] for k in range(m)]))
        cons += 1

    # (5) Each task assigned to exactly one start time
    for j in range(n):
        model.add_constraint(model.sum([S[j][t] for t in range(c - Ex_times[j] + 1)]) == 1)
        cons += 1
        # print(" + ".join([f"S[{j},{t}]" for t in range(c - Ex_times[j] + 1)]) + " = 1")

    # (6) S[j,t] ≤ sum_{τ=t-ti}^{t} S[i,τ] + 2 - X[i,k] - X[j,k] - W[i,k] - W[j,k] for i ≺ j
    for (i, j) in precedence_relations:
        if i > 0 and j > 0:
            for k in range(m):
                for t in range(c - Ex_times[j-1] + 1):
                    tau_range = range(t - Ex_times[i-1] + 1)
                    model.add_constraint(
                        S[j-1][t] 
                        <= model.sum([S[i-1][tau] for tau in tau_range]) 
                        + 2 - X[i-1][k] - X[j-1][k] - O[i-1][k] - O[j-1][k]
                    )
                    cons += 1

    # (7) X[i,k] + X[j,k] + sum_{τ=t-ti+1}^{t} S[i,τ] + sum_{τ=t-tj+1}^{t} S[j,τ] ≤ 3
    for i in range(n - 1):
        for j in range(i + 1, n):
            for k in range(m):
                for t in range(c):
                    model.add_constraint(
                        X[i][k] + X[j][k] + O[i][k] + O[j][k] +
                        model.sum([S[i][tau] for tau in  range(t - Ex_times[i] + 1, t + 1)]) +
                        model.sum([S[j][tau] for tau in  range(t - Ex_times[j] + 1, t + 1)])
                        <= 3
                    )
                    cons += 1

    # (8) Power peak constraint
    for t in range(c):
        model.add_constraint(
            model.sum([
                W[j] * model.sum([
                    S[j][s]
                    for s in range(max(0, t - Ex_times[j] + 1), t + 1)
                ])
                for j in range(n)
            ]) <= Wmax
        )
        cons += 1
        # print(" + ".join([f"{O[j]}*(" + " + ".join([f"S[{j},{s}]" for s in range(max(0, t - Ex_times[j]), t + 1)]) + ")" for j in range(n)]) + f" <= Wmax")


    # (9) Variable domains (already set by binary_var/integer_var)
    return model, cons

def solve_assignment_problem(n, m, c, Ex_times, precedence_relations, W):
    model, X, S, Wmax, O = create_assignment_model(n, m, c, CpoModel(), Ex_times)
    model, cons = add_assignment_constraints(
        n, m, c, model, X, S, O, Wmax, W, Ex_times, precedence_relations
    )
    model.set_parameters(LogVerbosity="Quiet", TimeLimit=3600)
    try:
        solution = model.solve()
        return solution, n*m+n*c, cons
    except Exception as e:
        return None, n*m+n*c, cons


def input_file(file_name):
    W = []
    precedence_relations = set()
    Ex_Time = []

    # Đọc file task_power
    with open(f"task_power/{file_name}.txt") as f:
        for line in f:
            W.append(int(line.strip()))

    # Đọc file data
    with open(f"data/{file_name}.IN2") as f:
        lines = f.readlines()

    n = int(lines[0])
    for idx, line in enumerate(lines[1:], start=1):
        line = line.strip()
        if idx > n:
            pair = tuple(map(int, line.split(',')))
            if pair == (-1, -1):
                break
            precedence_relations.add(pair)
        else:
            Ex_Time.append(int(line))

    return n, W, precedence_relations, Ex_Time

def get_value(solution, n, m, c, W, Ex_times):
    # From solution take X and S return matrix of scheduled tasks
    X_values = [[0 for _ in range(m)] for _ in range(n)]
    O_values = [[0 for _ in range(m)] for _ in range(n)]
    S_values = [[0 for _ in range(c)] for _ in range(n)]

    for i in range(n):
        for k in range(m):
            var_name = f"X_{i}_{k}"
            X_values[i][k] = solution.get_value(var_name)

    for i in range(n):
        for k in range(m):
            var_name = f"O_{i}_{k}"
            O_values[i][k] = solution.get_value(var_name)

    for i in range(n):
        for t in range(c):
            var_name = f"S_{i}_{t}"
            S_values[i][t] = solution.get_value(var_name)

    schedule = [[0 for _ in range(c)] for _ in range(m +1)]

    for k in range(m):
        for j in range(n):
            for t in range(c):
                for t0 in range(Ex_times[j]):
                    if (X_values[j][k] == 1 or O_values[j][k] == 1) and S_values[j][t - t0] == 1:
                        schedule[k][t] = W[j]

    #Last row = sum(schedule[j][t] for j in range(n))
    schedule[m] = [sum(schedule[j][t] for j in range(m)) for t in range(c)]
    peak = max(schedule[m])
    return schedule, solution.get_value("Wmax"), peak

def write_to_csv(result):
    output_dir = Path("Output")
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "result_cplex.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(result)

def optimal(filename):
    n, W, precedence_relations, Ex_times = input_file(filename[0])
    m = filename[1]  # Number of stations
    c = filename[2]  # Increased capacity to avoid infeasibility
    print(f"n={n}, m={m}, c={c}")
    start_time = time.time()
    solution, var, cons = solve_assignment_problem(n, m, c, Ex_times, precedence_relations, W)
    end_time = time.time()
    print("Time taken:", end_time - start_time)
    if solution and end_time - start_time < 3600:
        print(f"Solution for {filename[0]} with n={n}, m={m}, c={c}:")
        schedule, Wmax, peak = get_value(solution, n, m, c, W, Ex_times)
        print("Peak =", peak)
        write_to_csv([filename[0], n, m, c, peak, var, cons, end_time - start_time])
    else:
        print("No solution found.")
        write_to_csv([filename[0], n, m, c, "Timeout", var, cons, end_time - start_time])

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
    ["SAWYER", 7, 47]
]

for i in range(0, len(file_name)):
    optimal(file_name[i])