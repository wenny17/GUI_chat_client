import asyncio
import tkinter as tk


async def register_draw(login_queue):
    root = tk.Tk()
    root.geometry("300x100")
    root.title('registration')
    label = tk.Label(root, text="Please enter preffered nickname",
                     font="Arial 14")
    label.pack()
    input_frame = tk.Frame(root)
    input_frame.pack()
    input_field = tk.Entry(input_frame)
    input_field.pack(side="left", fill=tk.X, expand=True)
    input_field.bind("<Return>",
                     lambda event: get_login(root, input_field, login_queue))
    send_button = tk.Button(input_frame)
    send_button["text"] = "Send"
    send_button["command"] = lambda: get_login(root, input_field, login_queue)
    send_button.pack()

    await update_tk(root)


def get_login(root, input_field, queue):
    text = input_field.get()
    queue.put_nowait(text)
    input_field.delete(0, tk.END)
    root.destroy()


async def update_tk(root_frame, interval=1 / 120):
    while True:
        try:
            root_frame.update()
        except tk.TclError:
            return
        await asyncio.sleep(interval)
