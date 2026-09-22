import sys
import time
import csv
from pathlib import Path
from pysat.solvers import Cadical195
from pysat.pb import PBEnc, EncType

def generate_variables(m, n, c):
    X = [[i + 1 + j * n for i in range(n)] for j in range(m)]
    W = [[X[-1][-1] + i + 1 + j * n for i in range(n)] for j in range(m)]
    S = [[W[-1][-1] + i + 1 + j * n for i in range(n)] for j in range(c)]
    A = [[S[-1][-1] + i + 1 + j * n for i in range(n)] for j in range(c)]
    IN = [A[-1][-1] + i + 1 for i in range(n)]
    OUT = [IN[-1] + i + 1 for i in range(n)]
    return X, W, S, A, IN, OUT

def AMO(clauses, variables):
    for i in range(len(variables)):
        for j in range(i + 1, len(variables)):
            clauses.append([-variables[i], -variables[j]])

def setup(clause, m, n, c, X, W, S, A, IN, OUT, Ti, relation):
    for i in range(n):
        clause.append([X[j][i] for j in range(m)] + [W[j][i] for j in range(m)])
        AMO(clause, [X[j][i] for j in range(m)] + [W[j][i] for j in range(m)])
    for (i, j) in relation:
        for s in range(m):
            for k in range(s):
                clause.append([-X[s][i], -X[k][j]])
            for k in range(s + 1, m):
                clause.append([-W[s][i], -W[k][j]])
    for i, j in relation:
        for s in range(m):
            for s_ in range(m):
                clause.append([-W[s][i], -X[s_][j]])
    for i in range(n):
        clause.append([S[t][i] for t in range(0, c)])
        AMO(clause, [S[t][i] for t in range(0, c)])
    for i in range(n):
        for t0 in range(0, c):
            for t in range(t0, min(t0 + Ti[i], c)):
                clause.append([-S[t0][i], A[t][i]])
    for t in range(c):
        for s in range(m):
            for i in range(n):
                for j in range(n):
                    if i != j:
                        clause.append([-A[t][j], -A[t][i], -X[s][j], -X[s][i]])
                        clause.append([-A[t][j], -A[t][i], -W[s][j], -W[s][i]])
                        clause.append([-A[t][j], -A[t][i], -X[s][j], -W[s][i]])
    for i in range(n):
        for j in range(n):
            if i != j:
                for k in range(m):
                    for t in range(c):
                        for t1 in range(t):
                            clause.append([-S[t][i], -S[t1][j], -X[k][i], -W[k][j]])
    for (i, j) in relation:
        for t in range(c):
            for k in range(m):
                for t1 in range(t):
                    clause.append([-X[k][i], -X[k][j], -S[t][i], -S[t1][j]])
                    clause.append([-W[k][i], -W[k][j], -S[t][i], -S[t1][j]])
    for i in range(n):
        clause.append([-IN[i], -OUT[i]])
    for i in range(n):
        for j in range(m):
            clause.append([-X[j][i], IN[i]])
    for i in range(n):
        for j in range(m):
            clause.append([-W[j][i], OUT[i]])
    for i in range(n):
        for t in range(c - Ti[i] + 1, c):
            clause.append([-S[t][i]])

def read_file(file_name):
    W, relation, times = [], set(), []
    with open(f"task_power/{file_name}.txt") as f:
        for line in f:
            W.append(int(line.strip()))
    with open(f"data/{file_name}.IN2") as f:
        lines = f.readlines()
    n = int(lines[0])
    x_time_count = 0
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        if x_time_count < n:
            times.append(int(line))
            x_time_count += 1
        else:
            pair = tuple(map(int, line.split(',')))
            if pair == (-1, -1):
                break
            relation.add((pair[0] - 1, pair[1] - 1))
    return n, W, relation, times

def get_values(model, m, n, c, P, X, W, S, A, Ti, best_value=None):
    schedule = [[0 for _ in range(c)] for _ in range(m)]
    val = lambda var_id: model[abs(var_id) - 1] if model[abs(var_id) - 1] > 0 else model[abs(var_id) - 1]
    constraints = []

    X = [[val(X[k][j]) for j in range(n)] for k in range(m)]
    W = [[val(W[k][j]) for j in range(n)] for k in range(m)]
    S = [[val(S[t][j]) for j in range(n)] for t in range(c)]
    A = [[val(A[t][j]) for j in range(n)] for t in range(c)]

    for t in range(c):
        for k in range(m):
            for j in range(n):
                if A[t][j] > 0 and X[k][j] > 0:
                    schedule[k][t] = P[j]
                    constraints.append(-A[t][j])
                elif A[t][j] > 0 and W[k][j] > 0:
                    schedule[k][t] = -P[j]
                    constraints.append(-A[t][j])

    peak = [0 for _ in range(c)]
    for i in range(c):
        for k in range(m):
            peak[i] += abs(schedule[k][i])
    peak = int(max(peak))

    return schedule, peak, constraints

def log_to_csv(name, n, m, c, peak, sol, count, lenthclause, exec_time, status):
    """Add or update one CSV row for a unique filename/n/m/c combination."""
    log_file = Path("Output/res_cb.csv")
    header = [
        "Filename", "Tasks", "Machines", "Time cycle", "Peak",
        "Solutions times", "Variable Count", "Clause Length",
        "Execution Time", "Status",
    ]
    new_row = [name, n, m, c, peak, sol, count, lenthclause, f"{exec_time:.2f}", status]
    rows = []

    if log_file.exists() and log_file.stat().st_size > 0:
        with open(log_file, mode="r", newline="") as file:
            reader = csv.reader(file)
            next(reader, None)
            rows = list(reader)

    key = [str(name), str(n), str(m), str(c)]
    rows = [row for row in rows if row[:4] != key]
    rows.append(new_row)

    with open(log_file, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)

def optimize(n, m, c, name, P, relation, Ti):
    start_time = time.time()
    X, W, S, A, IN, OUT = generate_variables(m, n, c)
    clauses = []
    setup(clauses, m, n, c, X, W, S, A, IN, OUT, Ti, relation)
    
    solver = Cadical195()
    for clause in clauses:
        solver.add_clause(clause)
        
    result = solver.solve()
    sol = 0
    if result:
        model = solver.get_model()
        schedule, peak, new_constraints = get_values(model, m, n, c, P, X, W, S, A, Ti)
        count = OUT[-1] + 1
        lenthclause = len(clauses)
        
        # GHI NHẬN KẾT QUẢ BAN ĐẦU
        log_to_csv(name, n, m, c, peak, sol, count, lenthclause, time.time() - start_time, "FEASIBLE")
        print(f"[{name}] Initial Peak: {peak}")
        solver.add_clause(new_constraints)

        while True:
            sol += 1
            result = solver.solve()
            if result:
                model = solver.get_model()
                schedule, new_peak, new_constraints = get_values(
                    model, m, n, c, P, X, W, S, A, Ti, best_value=peak
                )
                solver.add_clause(new_constraints)
                if new_peak < peak:
                    peak = new_peak
                    # GHI ĐÈ KẾT QUẢ TỐT HƠN NGAY LẬP TỨC
                    log_to_csv(name, n, m, c, peak, sol, count, lenthclause, time.time() - start_time, "IMPROVED")
                    print(f"[{name}] New Peak: {peak}")
            else:
                print(f"[{name}] Optimal Peak: {peak}")
                log_to_csv(name, n, m, c, peak, sol, count, lenthclause, time.time() - start_time, "OPTIMAL")
                return peak
    else:
        log_to_csv(name, n, m, c, 0, 0, 0, len(clauses), time.time() - start_time, "UNSAT")
        return 0

if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(1)
    name = sys.argv[1]
    m = int(sys.argv[2])
    c = int(sys.argv[3])
    
    n, P, relation, Ti = read_file(name)
    optimize(n, m, c, name, P, relation, Ti)