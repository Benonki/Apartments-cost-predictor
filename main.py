import sys
from pathlib import Path

SCREENS_DIR = Path(__file__).resolve().parent / "screens"
sys.path.insert(0, str(SCREENS_DIR))

from MainScreen import ApartmentsApp


def main():
    app = ApartmentsApp()
    app.mainloop()


if __name__ == "__main__":
    main()