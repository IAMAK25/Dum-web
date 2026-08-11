import tkinter as tk
from tkinter import filedialog, messagebox

class App:
    def __init__(self, sender, receiver):
        self.sender = sender
        self.receiver = receiver

        self.root = tk.Tk()
        self.root.title("OptiTransfer")
        self.root.geometry("520x430")
        self.root.resizable(False, False)

        tk.Label(
            self.root,
            text="OPTITRANSFER",
            font=("Segoe UI", 24, "bold")
        ).pack(pady=(35, 5))

        tk.Label(
            self.root,
            text="Strict Stop-and-Wait Optical File Transfer",
            font=("Segoe UI", 11)
        ).pack(pady=(0, 25))

        self.button("SEND FILE", self.send)
        self.button("RECEIVE FILE", self.receive)
        self.button("EXIT", self.root.destroy)

        tk.Label(
            self.root,
            text=(
                "DATA #N is never followed by DATA #N+1\n"
                "until matching ACK #N is received."
            ),
            font=("Segoe UI", 9)
        ).pack(pady=25)

    def button(self, text, command):
        tk.Button(
            self.root,
            text=text,
            width=28,
            height=2,
            command=command
        ).pack(pady=8)

    def send(self):
        path = filedialog.askopenfilename(
            title="Select file to transfer"
        )

        if not path:
            return

        try:
            self.sender.run(path)
        except Exception as exc:
            messagebox.showerror(
                "Sender Error",
                str(exc)
            )

    def receive(self):
        try:
            self.receiver.run()
        except Exception as exc:
            messagebox.showerror(
                "Receiver Error",
                str(exc)
            )

    def run(self):
        self.root.mainloop()
