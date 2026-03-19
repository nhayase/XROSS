"""Entry point for ``python -m xross`` or the ``xross`` console script."""
import sys, os

if getattr(sys, '_MEIPASS', None):
    # PyInstaller: add bundle root to path
    _r = sys._MEIPASS
    if _r not in sys.path:
        sys.path.insert(0, _r)
    # Set working dir so favicon.ico is found next to exe
    os.chdir(os.path.dirname(sys.executable))

def main():
    from xross.gui.app import run
    run()

if __name__ == "__main__":
    main()
