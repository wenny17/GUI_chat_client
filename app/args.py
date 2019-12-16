import argparse
import os


DEFAULT_HISTORY_DIR = "chathistory.txt"
DEFAULT_HOST = "minechat.dvmn.org"
DEFAULT_PORT_R = 5000
DEFAULT_PORT_W = 5050


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-token",
        "-t",
        type=str,
        default=os.getenv("TOKEN"),
        help="Authorization token, if you haven't one, you can register"
    )

    parser.add_argument(
        "-host",
        type=str,
        default=os.getenv("HOST", DEFAULT_HOST)
    )

    parser.add_argument(
        "-port",
        type=int,
        default=os.getenv("READER_PORT", DEFAULT_PORT_R),
        help="port for read messages"
    )

    parser.add_argument(
        "-portw",
        type=int,
        default=os.getenv("WRITER_PORT") or DEFAULT_PORT_W,
        help="port for send messages"
    )

    parser.add_argument(
        "--history",
        type=str,
        default=os.getenv("HISTORY") or DEFAULT_HISTORY_DIR,
        help="history file directory",
        required=False
    )

    return parser.parse_args()
