"""
Ucdan uca test icin: icinde buyuk, net Ingilizce yazilar olan basit bir
pencere acar. Gercek bir oyun penceresinin yerini tutar. Bu pencere acik
kaldigi surece, Oyun Cevirmen programinin F9/F10 ile bu yazilari
bulup Turkceye cevirip ustune yazmasi beklenir.

Kullanim:
    venv\\Scripts\\python.exe tests\\test_pencere.py
"""
import tkinter as tk


def main():
    root = tk.Tk()
    root.title("Test Game Window")
    root.geometry("640x260+200+200")
    root.configure(bg="white")

    tk.Label(
        root, text="Press E to open the ancient door",
        font=("Segoe UI", 26, "bold"), bg="white", fg="black",
    ).pack(pady=30)

    tk.Label(
        root, text="Inventory is full",
        font=("Segoe UI", 26, "bold"), bg="white", fg="black",
    ).pack(pady=10)

    tk.Label(
        root, text="Game Over", font=("Segoe UI", 26, "bold"),
        bg="white", fg="black",
    ).pack(pady=10)

    root.attributes("-topmost", True)
    root.mainloop()


if __name__ == "__main__":
    main()
