from math import inf
import math
import time
import signal
from datetime import datetime
import signal
from pysat.solvers import Cadical195
import fileinput
import webbrowser
import sys
from pysat.pb import PBEnc, EncType
import csv
import html
from pathlib import Path

# begin
# khởi tạo các tập biến cần thiết ban đầu
def generate_variables(m , n ,c):
   # task i được gán vào cổng vào của máy j
   X = [ [i + 1 + j*n for i in range(n)] for j in range(m)]
   # task i được gán vào cổng ra của máy j
   W = [ [X[-1][-1] + i + 1 + j*n for i in range(n)] for j in range(m)]
   # task i được bắt đầu tại thời điểm t
   S = [ [W[-1][-1] + i + 1 + j*n for i in range(n)] for j in range(c)]
   # task i được xử lý tại thời điểm t
   A = [ [S[-1][-1] + i + 1 + j*n for i in range(n)] for j in range(c)]
   # task i đang ở cổng vào
   IN = [A[-1][-1] + i + 1 for i in range(n)]
   # task i đang ở cổng ra
   OUT = [IN[-1] + i + 1 for i in range(n)]

   
   return X , W , S , A , IN , OUT

def AMO(clauses , variables):
   for i in range(len(variables)):
      for j in range(i+1,len(variables)):
         clauses.append([-variables[i] , - variables[j]])

def setup(clause , m,n,c , X , W ,S, A ,IN,OUT, Ti , relation):
   
   # (1)đảm bảo mỗi công việc chỉ được thực hiện tại một trạm và một phía duy nhất
   for i in range(n):

      clause.append([X[j][i] for j in range(m) ] + [W[j][i] for j in range(m)])
      AMO(clause , [X[j][i] for j in range(m) ] + [W[j][i] for j in range(m) ])
   # (2)ràng buộc thứ tự ưu tiên
   for (i,j) in relation:
      for s in range(m):
         for k in range(s):
            clause.append([-X[s][i] , -X[k][j]])
         for k in range(s+1,m):
            clause.append([-W[s][i] , -W[k][j]])   

   # (3)ràng buộc việc ưu tiên không được ở cổng ra và công việc sau ở cổng vào
   for i,j in relation:
      for s in range(m):
         for s_ in range(m):
            clause.append([-W[s][i] , -X[s_][j]]) # nếu i đã ở đầu ra thì j không thể ở đầu vào
   
   # (4)đảm bảo công việc bắt đầu đúng 1 lần và hoàn thành trong chu kỳ c
   for i in range(n):
      clause.append([S[t][i] for t in range(0,c)])
      AMO(clause , [S[t][i] for t in range(0,c)])   

   # (5) đảm bảo máy chạy tại thời điểm t
   for i in range(n):
      for t0 in range(0,c):
         for t in range(t0,min(t0 + Ti[i], c)):
            clause.append([-S[t0][i], A[t][i]])
      
   # (6)ràng buộc non_overlap tại 1 trạm:
   for t in range(c):
      for s in range(m):
         for i in range(n):
               for j in range(n):
                  if i != j:
                     clause.append([-A[t][j], -A[t][i], -X[s][j], -X[s][i]])
                     clause.append([-A[t][j], -A[t][i], -W[s][j], -W[s][i]])
                     clause.append([-A[t][j], -A[t][i], -X[s][j], -W[s][i]])
   # (7)ràng buộc tại 1 máy thì in phải thực hiện trước out
   for i in range(n):
      for j in range(n):
         if i != j:
               for k in range(m): # Duyệt qua từng máy k
                  for t in range(c):
                     for t1 in range(t): # t1 < t
                           # Nếu i ở Lối vào máy k và j ở Lối ra máy k, thì j không được bắt đầu trước i
                           clause.append([-S[t][i], -S[t1][j], -X[k][i], -W[k][j]])

   # (8)ràng buộc công việc phụ thuộc phải được thực hiện lần lượt (xong rồi mới làm tiếp) trong cùng một máy
   for (i,j) in relation:
      for t in range(c):
         for k in range(m):
            for t1 in range(t):
               clause.append([-X[k][i],-X[k][j],-S[t][i] , -S[t1][j]])
               clause.append([-W[k][i],-W[k][j],-S[t][i] , -S[t1][j]])

   # (9) IN[i] -> - OUT[i]
   for i in range(n):
      clause.append([-IN[i], -OUT[i]])
   # (10) X[j][i] -> IN[i]
   for i in range(n):
      for j in range(m):
         clause.append([-X[j][i], IN[i]])
   # (11) W[j][i] -> OUT[i]
   for i in range(n):
      for j in range(m):
         clause.append([-W[j][i], OUT[i]])

   # (12) ngoài khoảng c - Ti[i] + 1 thì S[t][i] <0
   for i in range(n):
      for t in range(c - Ti[i] + 1, c):
         clause.append([-S[t][i]])

def read_file(file_name):
   W = []
   relation = set()
   times = []

   # đọc file task_power
   with open(f"task_power/{file_name}.txt") as f:
      for line in f:
            W.append(int(line.strip()))

   # Đọc file data
   with open(f"data/{file_name}.IN2") as f:                 
      lines = f.readlines()

   n = int(lines[0]) # số lượng task
   x_time_count = 0
   for line in lines[1:]:
      line = line.strip()
      if not line:  # Skip empty lines
         continue

      if x_time_count < n:
         times.append(int(line))
         x_time_count += 1
      else:
         pair = tuple(map(int, line.split(',')))
         if pair == (-1, -1):
            break
         # Input task ids are 1-based; normalize to 0-based for array access.
         relation.add((pair[0] - 1, pair[1] - 1))
   
   return n, W, relation, times

def get_values(model, m , n, c, P, X, W, S, A , Ti):
   schedule =  [[0 for t in range(c)] for k in range(m)]
   constraints = []

   # offset_X = 0
   # offset_W = m * n
   # offset_S = offset_W + (m * n)
   # offset_A = offset_E + (c * n)

   # X = [[model[offset_X + i * n + k] for k in range(n)] for i in range(m)]
   # W = [[model[offset_W + i * n + k] for k in range(n)] for i in range(m)]
   # S = [[model[offset_S + t * n + i] for i in range(n)] for t in range(c)]
   # A = [[model[offset_A + t * n + i] for i in range(n)] for t in range(c)]
   val = lambda var_id: model[abs(var_id) - 1] if model[abs(var_id) - 1] > 0 else model[abs(var_id) - 1]

    # Lấy giá trị Ma trận X, W, S, A dựa trên ma trận biến truyền vào
   X = [[val(X[k][j]) for j in range(n)] for k in range(m)]
   W = [[val(W[k][j]) for j in range(n)] for k in range(m)]
   
   S = [[val(S[t][j]) for j in range(n)] for t in range(c)]
   A = [[val(A[t][j]) for j in range(n)] for t in range(c)]
   
   # tạo ràng buộc loại trừ TH đã chạy
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

   peak = [0 for j in range(c)]
   for i in range(c):
      for k in range(m):
         peak[i] += abs(schedule[k][i])
   schedule.append(peak) # lưu bảng thông tin
   peak = int(max(peak))

   return schedule, peak, constraints

def optimize(n,m,c,name,P,relation,Ti):
   print("generation varialbes and constraints......")
   X , W , S , A ,IN ,OUT = generate_variables(m,n,c)
   n , P , relation , times = read_file(name)
   
   clauses = []
   setup(clauses,m,n,c,X,W,S,A,IN,OUT,times,relation)
   solver = Cadical195()
   for clause in clauses:
      solver.add_clause(clause)
   result = solver.solve()
   sol = 0
   print("first solve....")
   if result:
      model = solver.get_model()
      schedule, peak, new_constraints = get_values(model, m , n, c, P, X, W, S,A , Ti)
      print(f"Initial Peak: {peak}")
      count = OUT[-1] + 1
      while True:
         sol +=1
         solver = Cadical195()
         lenthclause = 0
         for clause in clauses:
            solver.add_clause(clause)
            lenthclause += 1
         # add constraints for optimize
         for i in range(c):
            lits =[]
            weights =[]
            for j in range(n):
               lits.append(A[i][j])
               weights.append(P[j])
               pb_constraint = PBEnc.leq(
                    lits=lits, 
                    weights=weights, 
                    bound=peak - 1, 
                    top_id=count, 
                    encoding=EncType.binmerge
                )            
            for clause in pb_constraint:
               solver.add_clause(clause)
               lenthclause += 1 
            if pb_constraint.nv > count:
               count = pb_constraint.nv + 1
         
         result = solver.solve()
         if result:
            model = solver.get_model()
            schedule, new_peak, new_constraints = get_values(model, m , n, c, P, X, W, S, A , Ti)
            if new_peak < peak:
               peak = new_peak
               print(f"New_Peak: {peak}")
            
         else:
            print(f"Optimal peak: {peak}")
            return peak, sol, count, lenthclause
   else:
      print("No solution found.")
   return 0, 1, count, lenthclause
   

file_name = [
    # Easy families 
    # MERTENS 
    ["MERTENS", 6, 6],      # 0
    ["MERTENS", 2, 18],     # 1
    ["MERTENS", 5, 7],      # 2
    ["MERTENS", 5, 8],      # 3
    ["MERTENS", 3, 10],     # 4
    ["MERTENS", 2, 15],     # 5
    # Easy/MERTENS count: 6

    # BOWMAN
    ["BOWMAN", 5, 20],      # 6
    # Easy/BOWMAN count: 1

    # JAESCHKE
    ["JAESCHKE", 8, 6],     # 7
    ["JAESCHKE", 3, 18],    # 8
    ["JAESCHKE", 6, 8],     # 9
    ["JAESCHKE", 4, 10],    # 10
    ["JAESCHKE", 3, 18],    # 11
    # Easy/JAESCHKE count: 5

    # JACKSON
    ["JACKSON", 8, 7],      # 12
    ["JACKSON", 3, 21],     # 13
    ["JACKSON", 6, 9],      # 14
    ["JACKSON", 5, 10],     # 15
    ["JACKSON", 4, 13],     # 16
    ["JACKSON", 4, 14],     # 17
    # Easy/JACKSON count: 6

    # MANSOOR
    ["MANSOOR", 4, 48],     # 18
    ["MANSOOR", 2, 94],     # 19
    ["MANSOOR", 3, 62],     # 20
    # Easy/MANSOOR count: 3

    # MITCHELL
    ["MITCHELL", 8, 14],    # 21
    ["MITCHELL", 3, 39],    # 22
    ["MITCHELL", 8, 15],    # 23
    ["MITCHELL", 5, 21],    # 24
    ["MITCHELL", 5, 26],    # 25
    ["MITCHELL", 3, 35],    # 26
    # Easy/MITCHELL count: 6

    # ROSZIEG
    ["ROSZIEG", 10, 14],    # 27
    ["ROSZIEG", 4, 32],     # 28
    ["ROSZIEG", 6, 25],     # 29
    ["ROSZIEG", 8, 16],     # 30
    ["ROSZIEG", 8, 18],     # 31
    ["ROSZIEG", 6, 21],     # 32
    # Easy/ROSZIEG count: 6

    # HESKIA
    ["HESKIA", 8, 138],     # 33
    ["HESKIA", 3, 342],     # 34
    ["HESKIA", 5, 205],     # 35
    ["HESKIA", 5, 216],     # 36
    ["HESKIA", 4, 256],     # 37
    ["HESKIA", 4, 324],     # 38
    # Easy/HESKIA count: 6

    # Easy families total count: 39

    # Hard families
    # BUXEY
    ["BUXEY", 7, 47],       # 39
    ["BUXEY", 8, 41],       # 40
    ["BUXEY", 11, 33],      # 41
    ["BUXEY", 13, 27],      # 42
    ["BUXEY", 12, 30],      # 43
    ["BUXEY", 7, 54],       # 44
    ["BUXEY", 10, 36],      # 45
    # Hard/BUXEY count: 7

    # SAWYER
    ["SAWYER", 14, 25],     # 46
    ["SAWYER", 7, 47],      # 47
    ["SAWYER", 8, 41],      # 48
    ["SAWYER", 12, 30],     # 49
    ["SAWYER", 13, 27],     # 50
    ["SAWYER", 11, 33],     # 51
    ["SAWYER", 10, 36],     # 52
    ["SAWYER", 7, 54],      # 53
    ["SAWYER", 5, 75],      # 54
    # Hard/SAWYER count: 9

    # GUNTHER
    ["GUNTHER", 9, 54],     # 55
    ["GUNTHER", 9, 61],     # 56
    ["GUNTHER", 14, 41],    # 57
    ["GUNTHER", 12, 44],    # 58
    ["GUNTHER", 11, 49],    # 59
    ["GUNTHER", 8, 69],     # 60
    ["GUNTHER", 7, 81],     # 61
    # Hard/GUNTHER count: 7

    # WARNECKE
    ["WARNECKE", 25, 65],   # 62
    ["WARNECKE", 31, 54],   # 63
    ["WARNECKE", 29, 56],   # 64
    ["WARNECKE", 29, 58],   # 65 
    ["WARNECKE", 27, 60],   # 66
    ["WARNECKE", 27, 62],   # 67
    ["WARNECKE", 24, 68],   # 68
    ["WARNECKE", 23, 71],   # 69
    ["WARNECKE", 22, 74],   # 70
    ["WARNECKE", 21, 78],   # 71
    ["WARNECKE", 20, 82],   # 72
    ["WARNECKE", 19, 86],   # 73
    ["WARNECKE", 17, 92],   # 74
    ["WARNECKE", 17, 97],   # 75
    ["WARNECKE", 15, 104],  # 76
    ["WARNECKE", 14, 111],  # 77
    # Hard/WARNECKE count: 16

    # Lutz2
    ["LUTZ2", 49, 11],      # 78
    ["LUTZ2", 44, 12],      # 79
    ["LUTZ2", 40, 13],      # 80
    ["LUTZ2", 37, 14],      # 81
    ["LUTZ2", 34, 15],      # 82
    ["LUTZ2", 31, 16],      # 83
    ["LUTZ2", 29, 17],      # 84
    ["LUTZ2", 28, 18],      # 85
    ["LUTZ2", 26, 19],      # 86
    ["LUTZ2", 25, 20],      # 87
    ["LUTZ2", 24, 21],      # 88
]

for name, m ,c in file_name[:5]:
   start_time = time.time()
   print(f"Running {name} with {m} machines and {c} time units")
   n , P ,relation , Ti = read_file(name)
   peak,sol,count,lenthclause = optimize(n,m,c,name,P,relation,Ti)
   end_time = time.time()
   print(f"Time taken: {end_time - start_time} seconds")
   # Viết kết quả vào file CSV
   with open('results.csv', mode='a', newline='') as file:
      writer = csv.writer(file)
      # Nếu file trống ghi tiêu đề
      if file.tell() == 0:
         writer.writerow(['Instance', 'Tasks', 'Machines', 'Time cycle', 'Peak', 'Solutions times', 'Variable Count', 'Clause Length', 'Execution Time'])
      writer.writerow([name, n, m, c, peak, sol, count, lenthclause, end_time - start_time])
   print("="*100)