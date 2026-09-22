import sys
import time
import csv
from pathlib import Path
from pysat. solvers import Cadical195
from pysat.pb import PBEnc, EncType

def generate_variables(m, n, c):
    X = [[i + 1 + j * n for i in range(n)] for j in range(m)]
    W = [[X[-1][-1] + i + 1 + j * n for i in range(n)] for j in range(m)]
    R = [[W[-1][-1] + i + 1 + j * n for i in range(n)] for j in range(2 * m)] # dùng để tạo AMO sequential counter cho X và W
    S = [[R[-1][-1] + i + 1 + j * n for i in range(n)] for j in range(c)]
    T = [[S[-1][-1] + i + 1 + j * n for i in range(n)] for j in range(c)] # dùng để tạo AMO sequential counter cho S
    A = [[T[-1][-1] + i + 1 + j * n for i in range(n)] for j in range(c)]
    return X, W, R, S, T, A

# def AMO(clauses, variables):
#     for i in range(len(variables)):
#         for j in range(i + 1, len(variables)): 
#             clauses.append([-variables[i], -variables[j]])
def AMO_sequential(clauses, variables, aux_vars):
    for i in range( len(variables)-1):
        clauses.append([-variables[i], aux_vars[i]])
    for i in range( len(aux_vars)-1):
        clauses.append([-aux_vars[i], aux_vars[i+1]])
    for i in range( len(aux_vars)-1):
        clauses.append([-aux_vars[i], -variables[i+1]])

def setup(clause, m, n, c, X, W, R, S, T, A, Ti, relation):
    # 1 - Each task can only be assigned to one machine at a time step
    for i in range(n):
        clause.append([X[j][i] for j in range(m)] + [W[j][i] for j in range(m)])
        AMO_sequential(clause, [X[j][i] for j in range(m)] + [W[j][i] for j in range(m - 1, -1, -1)], [R[j][i] for j in range( 2 * m-1)])
        """clause.append([-X[0][i], R[0][i]])
        clause.append([-R[0][i], X[0][i]])
        for k in range(1, 2 * m - 1):
            clause.append([R[k][i], -R[k - 1][i]])
            if k < m:
                clause.append([-X[k][i], R[k][i]])
                clause.append([-X[k][i], -R[k - 1][i]])
                clause.append([-R[k][i], R[k - 1][i], X[k][i]])
            if k >= m:
                clause.append([-W[2 * m - k - 1][i], R[k][i]])
                clause.append([-W[2 * m - k - 1][i], -R[k - 1][i]])
                clause.append([-R[k][i], R[k - 1][i], W[2 * m - k - 1][i]])

        clause.append([W[0][i], -R[2 * m - 2][i]])"""

            
            
    # 2 - Precedence constraints: machine gates
    for (i, j) in relation:
       for k in range(2 * m):
            if k < m:
               clause.append([-X[k][i], -R[k - 1][j]])
            if k >= m:
                clause.append([-W[2 * m - k - 1][i], -R[k - 1][j]])

    # 3 - Each task can only be started on one time step
    for i in range(n):
        clause.append([S[t][i] for t in range(0, c - Ti[i] + 1)])
        AMO_sequential(clause, [S[t][i] for t in range(0, c - Ti[i] + 1)],[T[t][i] for t in range( c - Ti[i])])

        """clause.append([-T[0][i], S[0][i]])
        clause.append([-S[0][i], T[0][i]])
        last_time = c - Ti[i] + 1
        for t in range(1, last_time - 1):
            clause.append([T[t][i], -T[t - 1][i]])
            clause.append([-S[t][i], T[t][i]])
            clause.append([-S[t][i], -T[t - 1][i]])
            clause.append([-T[t][i], T[t - 1][i], S[t][i]])

        clause.append([S[last_time - 1][i], -T[last_time - 2][i]])
        clause.append([-S[last_time - 1][i], T[last_time - 2][i]])"""


    # 4 - Each task can only be assigned at time steps that are within its processing time
    for i in range(n):
        for t0 in range(0, c):
            for t in range(t0, min(t0 + Ti[i], c)):
                clause.append([-S[t0][i], A[t][i]])

    # 5 - If task i is assigned to a machine at time t, then it cannot be assigned to any other machine at the same time step
    for t in range(c):
        for s in range(m):
            for i in range(n):
                for j in range(n):
                    if i != j:
                        clause.append([-A[t][j], -A[t][i], -X[s][j], -X[s][i]])
                        clause.append([-A[t][j], -A[t][i], -W[s][j], -W[s][i]])
                        clause.append([-A[t][j], -A[t][i], -X[s][j], -W[s][i]])

    # 6 - If task i is assigned to in gate, it cannot be assigned after task j in out gate
    for i in range(n):
        for j in range(n):
            if i != j:
                for k in range(m):
                    for t in range(c):
                        for t1 in range(t):
                            clause.append([-S[t][i], -S[t1][j], -X[k][i], -W[k][j]])

    # 7 - Precedence constraints: if task i is assigned to a machine at time t, then task j cannot be assigned before time t + Ti[i] - 1
    # task i and j must be assigned to the same machine
    for (i, j) in relation:
        for k in range(m):
            left = Ti[i] - 1
            right = c - Ti[j]
            clause.append([-X[k][i], -X[k][j], -T[left][j]])
            clause.append([-W[k][j], -W[k][i], -T[left][j]])
            clause.append([-X[k][i], -W[k][j], -T[left][j]])
            for t in range(left + 1, right):
                t_i = t - Ti[i] + 1
                clause.append([-X[k][i], -X[k][j], -S[t_i][i], -T[t][j]])
                clause.append([-W[k][j], -W[k][i], -S[t_i][i], -T[t][j]])
                clause.append([-X[k][i], -W[k][j], -S[t_i][i], -T[t][j]])

            for t in range(max(0, right - Ti[i] + 1), c - Ti[i] + 1):
                clause.append([-X[k][i], -X[k][j], -S[t][i], - T[c - Ti[j] - 1][j]])
                clause.append([-W[k][j], -W[k][i], -S[t][i], - T[c - Ti[j] - 1][j]])
                clause.append([-X[k][i], -W[k][j], -S[t][i], - T[c - Ti[j] - 1][j]])

    # 8 - Task cannot be assigned over fesible time steps
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

def get_values(model, m, n, c, P, X, W, S, A, Ti):
    schedule = [[0 for _ in range(c)] for _ in range(m)]
    constraints = []
    val = lambda var_id: model[abs(var_id) - 1] if model[abs(var_id) - 1] > 0 else model[abs(var_id) - 1]
    
    X = [[val(X[k][j]) for j in range(n)] for k in range(m)]
    W = [[val(W[k][j]) for j in range(n)] for k in range(m)]
    S = [[val(S[t][j]) for j in range(n)] for t in range(c)]
    A = [[val(A[t][j]) for j in range(n)] for t in range(c)]

    for i in range(c):
        for k in range(m):
            for j in range(n):
                if S[i][j] > 0 and (X[k][j] > 0 or W[k][j] > 0):
                    constraints.append(S[i][j])
                    for t in range(i, min(c, i + Ti[j])):
                        if X[k][j] > 0:
                            schedule[k][t] = P[j]
                        if W[k][j] > 0:
                            schedule[k][t] = -P[j]
                        constraints.append(-A[t][j])
    lpeak = [0 for _ in range(c)]
    for i in range(c):
        for k in range(m):
            lpeak[i] += abs(schedule[k][i])
    peak = int(max(lpeak))
    return schedule + [lpeak], peak, constraints

def log_to_csv(name, n, m, c, peak, sol, count, lenthclause, exec_time, status):
    """Add or update one CSV row for a unique filename/n/m/c combination."""
    log_file = Path("Output/res_pb_sq.csv")
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
    X, W, R, S, T, A = generate_variables(m, n, c)
    clauses = []
    setup(clauses, m, n, c, X, W, R, S, T, A, Ti, relation)
    
    solver = Cadical195()
    for clause in clauses:
        solver.add_clause(clause)
        
    result = solver.solve()
    sol = 0
    if result:
        model = solver.get_model()
        schedule, peak, new_constraints = get_values(model, m, n, c, P, X, W, S, A, Ti)
        count = A[-1][-1] + 1
        for line in schedule:
            print(line)
        lenthclause = len(clauses)
        
        # GHI NHẬN KẾT QUẢ BAN ĐẦU
        log_to_csv(name, n, m, c, peak, sol, count, lenthclause, time.time() - start_time, "FEASIBLE")
        print(f"[{name}] Initial Peak: {peak}")

        while True:
            sol += 1
            solver = Cadical195()
            lenthclause = len(clauses)
            for clause in clauses:
                solver.add_clause(clause)
            
            for i in range(c):
                lits, weights = [], []
                for j in range(n):
                    lits.append(A[i][j])
                    weights.append(P[j])
                pb_constraint = PBEnc.leq(
                    lits=lits, weights=weights, bound=peak - 1, top_id=count, encoding=EncType.binmerge
                )            
                for clause in pb_constraint:
                    solver.add_clause(clause)
                    lenthclause += 1 
                if pb_constraint.nv > count:
                    count = pb_constraint.nv + 1
            
            result = solver.solve()
            if result:
                model = solver.get_model()
                schedule, new_peak, new_constraints = get_values(model, m, n, c, P, X, W, S, A, Ti)
                if new_peak < peak:
                    peak = new_peak
                    # GHI ĐÈ KẾT QUẢ TỐT HƠN NGAY LẬP TỨC
                    log_to_csv(name, n, m, c, peak, sol, count, lenthclause, time.time() - start_time, "IMPROVED")
            else:
                print(f"[{name}] Optimal Peak: {peak}")
                log_to_csv(name, n, m, c, peak, sol, count, lenthclause, time.time() - start_time, "OPTIMAL")
                return peak
    else:
        print(f"[{name}] UNSAT")
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