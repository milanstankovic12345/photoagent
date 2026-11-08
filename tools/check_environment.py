"""Read-only environment diagnostics."""
import importlib.metadata
import importlib.util
import sys

print(sys.version)
print(sys.executable)
for name in ('Pillow', 'ImageHash', 'rawpy', 'pillow-heif', 'pytest'):
    try:
        print(name, importlib.metadata.version(name))
    except importlib.metadata.PackageNotFoundError:
        print(name, 'MISSING')
print('tkinter', importlib.util.find_spec('tkinter') is not None)
