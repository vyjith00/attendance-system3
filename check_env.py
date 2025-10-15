import sys, pkgutil, importlib
print('exe:', sys.executable)
print('sys.path:')
for p in sys.path:
    print(' ', p)
print('Flask found (pkgutil.find_loader):', pkgutil.find_loader('flask') is not None)
try:
    m = importlib.import_module('flask')
    print('flask module file:', getattr(m, '__file__', None))
except Exception as e:
    print('import error:', type(e).__name__, e)
