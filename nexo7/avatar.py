"""Small native always-on-top companion; original vector sprite, no GPU renderer."""
import json
from pathlib import Path
import sys
import threading
from urllib.parse import urlsplit,parse_qs
from urllib.request import Request,urlopen


def main():
    import tkinter as tk
    from tkinter import TclError
    path=Path(sys.argv[-1]);access=json.loads(path.read_text());parsed=urlsplit(access['url'])
    if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or not parsed.port:raise ValueError('Invalid local access file')
    token=parse_qs(parsed.fragment)['token'][0];base=f'http://127.0.0.1:{parsed.port}'
    root=tk.Tk();root.title('Nexo Navi');root.geometry('180x215+30+80');root.resizable(False,False)
    root.attributes('-topmost',True);root.configure(bg='#14213d')
    canvas=tk.Canvas(root,width=180,height=155,bg='#14213d',highlightthickness=0);canvas.pack()
    label=tk.Label(root,text='Nexo · idle',fg='#edf5ff',bg='#14213d');label.pack()
    state={'state':'idle','enabled':True,'unread':0};errors=[0];pending=[False]
    def request(endpoint,body=None):
        raw=None if body is None else json.dumps(body).encode()
        with urlopen(Request(base+endpoint,data=raw,headers={'X-Nexo-Key':token,'Content-Type':'application/json'}),timeout=4) as r:return json.load(r)
    def close():
        try:request('/api/navi/settings',{'settings':{'avatar':False}})
        except Exception:pass
        root.destroy()
    root.protocol('WM_DELETE_WINDOW',close)
    tk.Button(root,text='Open Nexo',command=lambda:__import__('webbrowser').open(access['url'])).pack()
    def draw():
        canvas.delete('all');phase=state['state'];color={'thinking':'#f1bf5a','listening':'#64dbcb','happy':'#bfa0ff','sleeping':'#77849b'}.get(phase,'#65a8ff')
        canvas.create_oval(35,12,145,122,fill=color,outline='')
        canvas.create_rectangle(46,58,134,98,fill='#14213d',outline='')
        for x in (68,112):
            if phase=='sleeping':canvas.create_line(x-8,79,x+8,79,fill='white',width=3)
            elif phase=='happy':canvas.create_arc(x-8,70,x+8,88,start=0,extent=180,style='arc',outline='white',width=3)
            else:canvas.create_oval(x-4,69,x+4,86,fill='white',outline='')
        canvas.create_polygon(60,115,120,115,133,143,47,143,fill=color,outline='')
        if state['unread']:canvas.create_oval(132,8,166,42,fill='#ef6a71',outline='');canvas.create_text(149,25,text=str(state['unread']),fill='white')
        label.configure(text='Nexo · '+phase)
    def fetch():
        try:
            data=request('/api/navi/presence');state.update(data);errors[0]=0
        except Exception:errors[0]+=1
        finally:pending[0]=False
    def poll():
        if not state['enabled'] or errors[0]>=3:root.destroy();return
        draw()
        if not pending[0]:pending[0]=True;threading.Thread(target=fetch,daemon=True).start()
        root.after(700,poll)
    poll();root.mainloop()

if __name__=='__main__':main()
