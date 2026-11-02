import sys, formulas, time
t=time.time()
xl = formulas.ExcelModel().loads(sys.argv[1]).finish()
sol = xl.calculate()
xl.write(dirpath=sys.argv[2])
print("calculated in", round(time.time()-t,1), "s")
