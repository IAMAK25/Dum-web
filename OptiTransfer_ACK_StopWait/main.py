from optitransfer.config import CONFIG
from optitransfer.sender import Sender
from optitransfer.receiver import Receiver
from optitransfer.ui import App

def main():
    App(Sender(CONFIG), Receiver(CONFIG)).run()

if __name__ == "__main__":
    main()
