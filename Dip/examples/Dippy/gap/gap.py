#!/usr/bin/env python

# Generalized Assignment Problem
# argument should be a problem file, see Dip/examples/GAP_Instance.cpp for format
# for an e.g. see gap0512-2.dat included in this directory

import sys

from pulp import LpVariable, LpBinary, lpSum, value, LpProblem, LpMaximize

try:
    import path
except ImportError:
    pass
        
try:
    import dippy
except ImportError:
    try:
        import src.dippy as dippy
    except ImportError:
        import coinor.dippy as dippy

debug_print = False

tol = pow(pow(2, -24), 2.0 / 3.0)

# parse data file
input = open(sys.argv[1])

line = input.readline().split()
NUM_MACHINES = int(line[0])
NUM_TASKS = int(line[1])
MACHINES = range(NUM_MACHINES)
TASKS = range(NUM_TASKS)
MACHINES_TASKS = [(m, t) for m in MACHINES for t in TASKS]

COSTS = []
for m in MACHINES:
    line = input.readline().split()
    assert len(line) == NUM_TASKS
    COSTS.append([int(f) for f in line])

RESOURCE_USE = []
for m in MACHINES:
    line = input.readline().split()
    assert len(line) == NUM_TASKS
    RESOURCE_USE.append([int(f) for f in line])

line = input.readline().split()
assert len(line) == NUM_MACHINES
CAPACITIES = [int(f) for f in line]


assignVars = []
for m in MACHINES:
    v = []
    for t in TASKS:
        v.append(LpVariable("M%dT%d" % (m, t), cat=LpBinary))
    assignVars.append(v)

prob = dippy.DipProblem("GAP",
                        display_mode = 'off', 
                        layout = 'dot',
                        display_interval = None,
                        )

# objective
prob += lpSum(assignVars[m][t] * COSTS[m][t] for m, t in MACHINES_TASKS), "min"

# machine capacity (knapsacks, relaxation)
for m in MACHINES:
    prob.relaxation[m] += lpSum(assignVars[m][t] * RESOURCE_USE[m][t] for t in TASKS) <= CAPACITIES[m]

# assignment
for t in TASKS:
    prob += lpSum(assignVars[m][t] for m in MACHINES) == 1

def solve_subproblem(prob, machine, redCosts, target):
    if debug_print:
        print "solve_subproblem..."
        print redCosts
   
    # get tasks which have negative reduced costs
    task_idx = [t for t in TASKS if redCosts[assignVars[machine][t]] < 0]
    var = [assignVars[machine][t] for t in task_idx]
    obj = [-redCosts[assignVars[machine][t]] for t in task_idx]
    weights = [RESOURCE_USE[machine][t] for t in task_idx]

    z, solution = knapsack01(obj, weights, CAPACITIES[machine])

    # Get the reduced cost of the knapsack solution and waste
    if debug_print:
        print [(v, redCosts[v]) for v in var]
        print obj
        print "z, solution =", z, solution
        print "rc", -z
    # Return the solution if the reduced cost is low enough
    # ...
    if z < -tol: # ... or an empty location is "useful"
        if debug_print:
            print "Empty solution is optimal"
        return [{}]

    var_values = dict([(var[i], 1) for i in solution])

    if debug_print:
        rcCheck = 0.0
        for v in var_values.keys():
            rcCheck += redCosts[v] * var_values[v]
        print "Checking rc calc", -z, rcCheck 
        print var_values
    return [var_values]

def knapsack01(obj, weights, capacity):
    """ 0/1 knapsack solver, maximizes profit. weights and capacity integer """
        
    debug_subproblem = False
    
    assert len(obj) == len(weights)
    n = len(obj)
    if n == 0:
        return 0, []

    if (debug_subproblem):
        relaxation = LpProblem('relaxation', LpMaximize)
        relax_vars = [str(i) for i in range(n)]
        var_dict   = LpVariable.dicts("", relax_vars, 0, 1, LpBinary)
        relaxation += lpSum(var_dict[str(i)] * weights[i] for i in range(n)) <= capacity
        relaxation += lpSum(var_dict[str(i)] * obj[i] for i in range(n))
        relaxation.solve()
        relax_obj = value(relaxation.objective)

        solution =  [i for i in range(n) if var_dict[str(i)].varValue > tol ]

        print relax_obj, solution


    c = [[0]*(capacity+1) for i in range(n)]
    added = [[False]*(capacity+1) for i in range(n)]
    # c [items, remaining capacity]
    # important: this code assumes strictly positive objective values
    for i in range(n):
        for j in range(capacity+1):
            if (weights[i] > j):
                c[i][j] = c[i-1][j]
            else:
                c_add = obj[i] + c[i-1][j-weights[i]]
                if c_add > c[i-1][j]:
                    c[i][j] = c_add
                    added[i][j] = True
                else:
                    c[i][j] = c[i-1][j]

    # backtrack to find solution
    i = n-1
    j = capacity

    solution = []
    while i >= 0 and j >= 0:
        if added[i][j]:
            solution.append(i)
            j -= weights[i]
        i -= 1
        
    return c[n-1][capacity], solution

prob.relaxed_solver = solve_subproblem

dippy.Solve(prob, {
    'TolZero': '%s' % tol,
    'doPriceCut': '1',
#    'logLevel': '3', 
})

for m in MACHINES:
    print 
    print "Machine %d assigned tasks" %m,
    for t in TASKS:
        v = assignVars[m][t].varValue
        if v:
            print "%d" %t,
            
if prob.display_mode != 'off':
    if (prob.Tree.attr['display'] == 'pygame') or (prob.Tree.attr['display'] == 'xdot'):
        prob.Tree.display()

