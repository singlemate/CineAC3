"""Dependency-free desktop frontend. Run with Python including Tk."""
import ctypes
import json
import os
import queue
import subprocess
import threading
import time
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from engine import command, verify, duration, find_tool

class App(tk.Tk):
    def __init__(self):
        # Declare DPI awareness before Tk creates any Windows handles.
        if os.name == 'nt':
            try:
                ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            except (AttributeError, OSError):
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(2)
                except (AttributeError, OSError):
                    pass
        super().__init__()
        self.title('CineAC3 — DTS → AC3')
        self.ui_scale = max(1.0, float(self.tk.call('tk', 'scaling')) / (96 / 72))
        px = lambda value: max(1, round(value * self.ui_scale))
        self.px = px
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = min(px(1120), sw-px(48)), min(px(760), sh-px(80))
        self.geometry(f'{width}x{height}+{max(0,(sw-width)//2)}+{max(0,(sh-height)//2-px(20))}')
        self.minsize(min(px(860), width), min(px(570), height))
        self.configure(bg='#f3f5f3')
        self.jobs, self.events = {}, queue.Queue()
        self.busy, self.proc = False, None
        self.cancelled = threading.Event()
        self.ffmpeg, self.ffprobe = find_tool('ffmpeg'), find_tool('ffprobe')
        self.controls = []
        self.log_visible = False
        style = ttk.Style(self)
        style.theme_use('clam')
        bg, paper, ink, muted, line = '#f3f5f3', '#ffffff', '#203731', '#64756e', '#dbe3de'
        accent = '#116f5b'
        style.configure('.', font=('Segoe UI', 10), background=bg, foreground=ink)
        style.configure('TFrame', background=bg)
        style.configure('Card.TFrame', background=paper)
        style.configure('TLabel', background=bg, foreground=ink)
        style.configure('Muted.TLabel', foreground=muted)
        style.configure('Title.TLabel', font=('Segoe UI', 26, 'bold'), foreground='#163d32')
        style.configure('Badge.TLabel', background='#e0eee6', foreground=accent,
                        padding=(px(12), px(7)), font=('Segoe UI', 10, 'bold'))
        style.configure('TButton', background=paper, foreground=ink, bordercolor=line,
                        lightcolor=paper, darkcolor=paper, borderwidth=1,
                        padding=(px(15), px(10)), focuscolor=accent)
        style.map('TButton', background=[('disabled', '#edf0ed'), ('pressed', '#dbe8e0'), ('active', '#e6eee9')],
                  foreground=[('disabled', '#97a39d')])
        style.configure('Primary.TButton', background=accent, foreground='white',
                        bordercolor=accent, lightcolor=accent, darkcolor=accent,
                        font=('Segoe UI', 10, 'bold'))
        style.map('Primary.TButton', background=[('disabled', '#dbe5df'), ('pressed', '#095340'), ('active', '#0b8066')],
                  foreground=[('disabled', '#899b91'), ('!disabled', 'white')],
                  bordercolor=[('disabled', '#dbe5df'), ('!disabled', accent)])
        style.configure('TCheckbutton', background=bg, foreground=ink, padding=px(4),
                        indicatorbackground=paper, indicatorforeground=accent,
                        indicatorsize=px(16), indicatormargin=(px(2), px(3), px(7), px(3)))
        style.map('TCheckbutton', background=[('active', bg)], foreground=[('disabled', '#97a39d')],
                  indicatorbackground=[('selected', '#d7eee3'), ('!selected', paper)])
        style.configure('TCombobox', fieldbackground=paper, background='#e5ece7',
                        foreground=ink, arrowcolor=accent, bordercolor=line, padding=px(7))
        style.map('TCombobox', fieldbackground=[('readonly', paper), ('disabled', '#edf0ed')],
                  foreground=[('readonly', ink), ('disabled', '#97a39d')],
                  selectbackground=[('readonly', paper)], selectforeground=[('readonly', ink)])
        self.option_add('*TCombobox*Listbox.background', paper)
        self.option_add('*TCombobox*Listbox.foreground', ink)
        self.option_add('*TCombobox*Listbox.selectBackground', '#d9eee3')
        self.option_add('*TCombobox*Listbox.selectForeground', '#163d32')
        style.configure('Treeview', background=paper, fieldbackground=paper, foreground=ink,
                        rowheight=px(37), indent=px(20), borderwidth=0, font=('Segoe UI', 10))
        style.configure('Treeview.Heading', background='#e8eee9', foreground='#435b50',
                        font=('Segoe UI', 10, 'bold'), padding=(px(12), px(11)), relief='flat')
        style.map('Treeview', background=[('selected', '#dceee4')], foreground=[('selected', '#133e2d')])
        style.map('Treeview.Heading', background=[('active', '#dce7df')])
        style.configure('Horizontal.TProgressbar', background=accent, troughcolor='#e0e8e2',
                        borderwidth=0, lightcolor=accent, darkcolor=accent, thickness=px(7))
        style.configure('Vertical.TScrollbar', background='#c7d6cd', troughcolor=paper,
                        arrowcolor='#627b6d', borderwidth=0, arrowsize=px(12))
        style.configure('Horizontal.TScrollbar', background='#c7d6cd', troughcolor=paper,
                        arrowcolor='#627b6d', borderwidth=0, arrowsize=px(12))

        box = ttk.Frame(self, padding=px(26))
        box.pack(fill='both', expand=True)
        box.columnconfigure(0, weight=1)
        box.rowconfigure(3, weight=1)
        header = ttk.Frame(box)
        header.grid(row=0, column=0, sticky='ew')
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text='CineAC3', style='Title.TLabel').grid(row=0, column=0, sticky='w')
        self.quality_badge = ttk.Label(header, text='640 кбит/с · максимум AC3', style='Badge.TLabel')
        self.quality_badge.grid(row=0, column=1, sticky='e')
        subtitle = ttk.Label(box, text='DTS → AC3 · Звук для вашего телевизора. Видео без перекодирования.', style='Muted.TLabel')
        subtitle.grid(row=1, column=0, sticky='w', pady=(px(3), px(22)))

        bar = ttk.Frame(box)
        bar.grid(row=2, column=0, sticky='ew', pady=(0, px(14)))
        bar.columnconfigure(2, weight=1)
        for column, (title, action) in enumerate([('Добавить фильмы…', self.choose), ('Очистить', self.clear)]):
            button = ttk.Button(bar, text=title, command=action)
            button.grid(row=0, column=column, padx=(0, px(8)))
            self.controls.append(button)
        self.start_button = ttk.Button(bar, text='Конвертировать очередь', command=self.start, style='Primary.TButton')
        self.start_button.grid(row=0, column=3, sticky='e')
        self.controls.append(self.start_button)
        self.stop = ttk.Button(bar, text='Отменить', command=self.cancel, state='disabled')
        self.stop.grid(row=0, column=4, padx=(px(8), 0))

        table = ttk.Frame(box, style='Card.TFrame', padding=1)
        table.grid(row=3, column=0, sticky='nsew')
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(table, columns=('format', 'status'), selectmode='browse', height=7)
        self.tree.heading('#0', text='Фильм и аудиодорожки')
        self.tree.heading('format', text='Формат')
        self.tree.heading('status', text='Состояние')
        self.tree.column('#0', width=px(560), minwidth=px(300), stretch=True)
        self.tree.column('format', width=px(180), minwidth=px(120), stretch=False)
        self.tree.column('status', width=px(190), minwidth=px(140), stretch=False)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(table, orient='horizontal', command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.bind('<Button-1>', self.toggle)
        self.tree.bind('<space>', self.toggle_key)
        self.tree.tag_configure('file', font=('Segoe UI', 10, 'bold'), background='#f1f6f2')
        self.tree.tag_configure('error', foreground='#a13e31')

        settings = ttk.Frame(box)
        settings.grid(row=4, column=0, sticky='ew', pady=(px(16), px(10)))
        ttk.Label(settings, text='Качество AC3', font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky='w')
        self.rate = tk.StringVar(value='640')
        self.rate.trace_add('write', lambda *_: self.quality_badge.configure(
            text=f'{self.rate.get()} кбит/с' + (' · максимум AC3' if self.rate.get() == '640' else ' · AC3')))
        combo = ttk.Combobox(settings, textvariable=self.rate,
            values=('640', '448', '384', '320', '256', '192'), state='readonly', width=6,
            font=('Segoe UI', 10))
        combo.grid(row=0, column=1, padx=(px(12), px(7)))
        self.controls.append(combo)
        ttk.Label(settings, text='кбит/с', style='Muted.TLabel').grid(row=0, column=2, sticky='w')
        self.force = tk.BooleanVar(value=True)
        check = ttk.Checkbutton(settings, text='Выводить выбранный звук в 5.1', variable=self.force)
        check.grid(row=0, column=3, padx=(px(28), 0), sticky='w')
        self.controls.append(check)
        note = ttk.Label(box, style='Muted.TLabel', text='Оригиналы сохраняются. Новый MKV появится рядом с фильмом.\n'
                         'Отметьте звук для конвертации. Остальные дорожки и вложения копируются.')
        note.grid(row=5, column=0, sticky='ew', pady=(0, px(16)))
        self.progress = ttk.Progressbar(box, maximum=100)
        self.progress.grid(row=6, column=0, sticky='ew')
        footer = ttk.Frame(box)
        footer.grid(row=7, column=0, sticky='ew', pady=(px(10), 0))
        footer.columnconfigure(0, weight=1)
        self.status = tk.StringVar(value='Добавьте фильмы или перетащите их в окно')
        self.status_label = ttk.Label(footer, textvariable=self.status, style='Muted.TLabel')
        self.status_label.grid(row=0, column=0, sticky='ew', padx=(0, px(12)))
        self.log_button = ttk.Button(footer, text='Журнал ▾', command=self.toggle_log)
        self.log_button.grid(row=0, column=1, sticky='e')
        footer.bind('<Configure>', lambda e: self.status_label.configure(wraplength=max(px(200), e.width-px(140))))
        self.log_frame = ttk.Frame(box)
        self.log_frame.grid(row=8, column=0, sticky='ew', pady=(px(10), 0))
        self.log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(self.log_frame, height=4, bg=paper, fg='#496056',
            font=('Consolas', 9), state='disabled', relief='flat', borderwidth=0,
            highlightthickness=1, highlightbackground=line, padx=px(12), pady=px(8), wrap='word')
        self.log.grid(row=0, column=0, sticky='ew')
        log_scroll = ttk.Scrollbar(self.log_frame, orient='vertical', command=self.log.yview)
        log_scroll.grid(row=0, column=1, sticky='ns')
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log_frame.grid_remove()
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.after(100, self.poll)
        self.after(200, self.enable_drop)
        self.write('Готово. Нажмите на аудиодорожку, чтобы включить или снять галочку.')
        if self.ffmpeg and self.ffprobe:
            self.write('Встроенный модуль конвертации готов. Настройка не требуется.')
        else:
            self.write('Первый запуск: готовим модуль конвертации. Нужен интернет (около 115 МБ).')
            self.after(300, lambda: self.work(self.install_tools))

    def install_tools(self):
        from bootstrap import install
        def progress(received, total):
            self.events.put(('setup', (received, total)))
        try:
            install(progress, self.cancelled)
            self.ffmpeg, self.ffprobe = find_tool('ffmpeg'), find_tool('ffprobe')
            if not self.ffmpeg or not self.ffprobe:
                raise RuntimeError('Модуль не найден после установки')
            self.events.put(('log', 'Модуль установлен. Можно добавлять фильмы.'))
        except Exception as exc:
            self.events.put(('setup_error', str(exc)))

    def toggle_log(self):
        self.log_visible = not self.log_visible
        if self.log_visible:
            self.log_frame.grid()
        else:
            self.log_frame.grid_remove()
        self.log_button.configure(text='Скрыть журнал ▴' if self.log_visible else 'Журнал ▾')

    def enable_drop(self):
        if os.name!='nt': return
        from ctypes import wintypes
        user=ctypes.windll.user32; shell=ctypes.windll.shell32
        hwnd=self.winfo_id()
        user.GetParent.argtypes=[wintypes.HWND]; user.GetParent.restype=wintypes.HWND
        hwnd=user.GetParent(hwnd) or hwnd
        callback=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM)
        setproc=user.SetWindowLongPtrW
        setproc.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_void_p]; setproc.restype=ctypes.c_void_p
        user.CallWindowProcW.argtypes=[ctypes.c_void_p,wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
        user.CallWindowProcW.restype=ctypes.c_ssize_t
        shell.DragQueryFileW.argtypes=[wintypes.HANDLE,wintypes.UINT,wintypes.LPWSTR,wintypes.UINT]
        shell.DragFinish.argtypes=[wintypes.HANDLE]
        shell.DragAcceptFiles.argtypes=[wintypes.HWND,wintypes.BOOL]
        def handler(h,msg,w,l):
            if msg==0x233:
                files=[]
                for i in range(shell.DragQueryFileW(w,0xffffffff,None,0)):
                    size=shell.DragQueryFileW(w,i,None,0)+1
                    buf=ctypes.create_unicode_buffer(size)
                    shell.DragQueryFileW(w,i,buf,size); files.append(buf.value)
                shell.DragFinish(w)
                self.after(0,lambda:self.add_files(files))
                return 0
            return user.CallWindowProcW(self.old_proc,h,msg,w,l)
        self.drop_callback=callback(handler)
        self.old_proc=setproc(hwnd,-4,ctypes.cast(self.drop_callback,ctypes.c_void_p))
        shell.DragAcceptFiles(hwnd,True)
        self.drop_hwnd,self.setproc=hwnd,setproc

    def write(self,text):
        self.log.configure(state='normal'); self.log.insert('end',str(text)+'\n'); self.log.see('end'); self.log.configure(state='disabled')

    def lock(self,value):
        self.busy=value
        for w in self.controls:
            w.configure(state='disabled' if value else ('readonly' if isinstance(w,ttk.Combobox) else 'normal'))
        self.stop.configure(state='normal' if value else 'disabled')

    def choose(self):
        self.add_files(filedialog.askopenfilenames(title='Выберите фильмы',filetypes=[('Видео','*.mkv *.mp4 *.avi *.mov *.ts *.m2ts *.webm'),('Все файлы','*.*')]))

    def clear(self):
        self.jobs.clear(); self.tree.delete(*self.tree.get_children())

    def toggle_key(self,event):
        self.toggle_id(self.tree.focus()); return 'break'

    def toggle(self,event):
        if self.tree.identify_column(event.x)=='#0': self.toggle_id(self.tree.identify_row(event.y))

    def toggle_id(self,iid):
        if self.busy:return
        for j in self.jobs.values():
            if iid in j['tracks']:
                t=j['tracks'][iid]; t['selected']=not t['selected']
                self.tree.item(iid,text=('☑ ' if t['selected'] else '☐ ')+t['label']); break

    def add_files(self,files):
        if self.busy:return
        self.ffprobe=self.ffprobe or find_tool('ffprobe'); self.ffmpeg=self.ffmpeg or find_tool('ffmpeg')
        if not self.ffprobe:
            messagebox.showerror('Компоненты программы','Не хватает встроенного модуля анализа. Восстановите полную папку приложения.');return
        known={j['path'] for j in self.jobs.values()}; added=[]
        for f in files:
            p=Path(f).resolve()
            if not p.is_file() or p in known:continue
            known.add(p); iid=self.tree.insert('','end',text=p.name,values=('','Анализ…'),open=True,tags=('file',))
            j=dict(path=p,iid=iid,info=None,tracks={});self.jobs[iid]=j;added.append(j)
        if added:self.work(self.inspect,added)

    def work(self,target,*args):
        self.cancelled.clear(); self.lock(True)
        self.thread=threading.Thread(target=self.worker,args=(target,args),daemon=True);self.thread.start()

    def worker(self,target,args):
        try:target(*args)
        except Exception as exc:self.events.put(('log',str(exc)))
        finally:self.events.put(('done',None))

    def capture(self,tool,args,timeout=120):
        with subprocess.Popen([tool]+list(map(str,args)),stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)) as p:
            self.proc=p; deadline=time.monotonic()+timeout
            while True:
                try:out,err=p.communicate(timeout=.2);break
                except subprocess.TimeoutExpired:
                    if self.cancelled.is_set() or time.monotonic()>deadline:
                        p.kill();p.communicate();raise RuntimeError('Отменено / превышено время ожидания')
            self.proc=None
            if p.returncode:raise RuntimeError(err.decode('utf-8',errors='replace')[-16000:])
            return out

    def probe(self,file):
        return json.loads(self.capture(self.ffprobe,['-v','error','-show_streams','-show_format','-show_chapters','-of','json',file]))

    def inspect(self,jobs):
        for j in jobs:
            if self.cancelled.is_set():break
            try:
                info=self.probe(j['path'])
                if not info.get('streams'):raise ValueError('В файле нет потоков')
                self.events.put(('info',(j,info)))
            except Exception as exc:self.events.put(('error',(j,str(exc))))

    def start(self):
        self.ffmpeg=self.ffmpeg or find_tool('ffmpeg')
        if not self.ffmpeg:messagebox.showerror('Компоненты программы','Не хватает встроенного модуля конвертации. Восстановите полную папку приложения.');return
        tasks=[]
        for j in self.jobs.values():
            selected={t['index'] for t in j['tracks'].values() if t['selected']}
            if j['info'] and selected:tasks.append((j,selected))
        if not tasks:messagebox.showinfo('Дорожки','Добавьте фильм и отметьте аудиодорожку.');return
        self.work(self.convert,tasks,int(self.rate.get()),self.force.get())

    def convert(self,tasks,rate,force):
        for j,selected in tasks:
            if self.cancelled.is_set():break
            source=j['path']; target=source.with_name(source.stem+'_AC3.mkv');n=2
            while target.exists():target=source.with_name(f'{source.stem}_AC3_{n}.mkv');n+=1
            token=uuid.uuid4().hex;partial=target.with_name(target.stem+'.'+token+'.partial.mkv')
            logpath=target.with_name(target.stem+'.'+token[:8]+'.log')
            try:
                args=command(source,partial,j['info'],selected,rate,force)
                self.events.put(('state',(j,'Конвертация…')))
                with logpath.open('x',encoding='utf-8') as log:
                    log.write(json.dumps([self.ffmpeg]+args,ensure_ascii=False)+'\n');log.flush()
                    with subprocess.Popen([self.ffmpeg]+args,stdout=subprocess.PIPE,stderr=log,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)) as p:
                        self.proc=p
                        if self.cancelled.is_set():p.kill()
                        for raw in p.stdout:
                            if self.cancelled.is_set():p.kill();break
                            key,_,value=raw.decode(errors='replace').strip().partition('=')
                            if key=='out_time_us' and duration(j['info']):
                                try:self.events.put(('progress',(j,min(99,max(0,int(int(value)/1e6/duration(j['info'])*100))))))
                                except ValueError:pass
                        p.wait();self.proc=None
                        if p.returncode:raise RuntimeError(f'FFmpeg: код {p.returncode}. Журнал: {logpath}')
                if self.cancelled.is_set():raise RuntimeError('Отменено')
                self.events.put(('state',(j,'Проверка…')))
                verify(j['info'],self.probe(partial),selected,force)
                if self.cancelled.is_set():raise RuntimeError('Отменено')
                if target.exists():raise FileExistsError('Выходной файл уже существует')
                partial.rename(target)
                self.events.put(('state',(j,'Готово')));self.events.put(('log','Сохранено: '+str(target)))
                self.events.put(('progress',(j,100)))
            except Exception as exc:self.events.put(('error',(j,str(exc))))
            finally:
                try:partial.unlink(missing_ok=True)
                except OSError:self.events.put(('log','Остался временный файл: '+str(partial)))

    def poll(self):
        try:
            while True:
                kind,data=self.events.get_nowait()
                if kind=='done':self.lock(False);self.status.set('Отменено' if self.cancelled.is_set() else 'Готово. Проверьте состояния файлов.')
                elif kind=='log':self.write(data)
                elif kind=='setup':
                    received,total=data
                    self.status.set(f'Подготовка модуля: {received//1048576} МБ' + (f' из {total//1048576} МБ' if total else ''))
                    if total:self.progress['value']=min(99,received/total*100)
                elif kind=='setup_error':
                    self.write('Не удалось подготовить модуль: '+data)
                    if not self.log_visible:self.toggle_log()
                elif kind=='info':
                    j,info=data;j['info']=info
                    for s in info['streams']:
                        tags=s.get('tags',{});codec=s.get('codec_name','?');kind=s.get('codec_type','?')
                        label=f"#{s['index']} {kind} {tags.get('language','')} {tags.get('title','')}"
                        audio=kind=='audio';selected=codec=='dts'
                        iid=self.tree.insert(j['iid'],'end',text=(('☑ ' if selected else '☐ ') if audio else '')+label,
                            values=(codec+(f" · {s.get('channels','?')} ch" if audio else ''),''))
                        if audio:j['tracks'][iid]=dict(index=s['index'],selected=selected,label=label)
                    self.tree.set(j['iid'],'status','Выберите дорожки')
                elif kind in ('state','error'):
                    j,text=data;self.tree.set(j['iid'],'status','Ошибка' if kind=='error' else text)
                    self.status.set(j['path'].name+' — '+text)
                    if kind=='error':self.write(j['path'].name+': '+text)
                elif kind=='progress':
                    j,value=data;self.progress['value']=value
                    if value<100:self.tree.set(j['iid'],'status',str(value)+'%')
        except queue.Empty:pass
        self.after(100,self.poll)

    def cancel(self):
        self.cancelled.set()
        if self.proc:
            try:self.proc.kill()
            except OSError:pass

    def close(self):
        if self.busy:
            if not messagebox.askyesno('Выход','Отменить операцию и закрыть?'):return
            self.cancel();self.after(100,self.finish_close);return
        self.finish_close()

    def finish_close(self):
        if self.busy:self.after(100,self.finish_close);return
        if hasattr(self,'old_proc'):self.setproc(self.drop_hwnd,-4,self.old_proc)
        for timer in self.tk.call('after', 'info'):
            self.after_cancel(timer)
        self.destroy()

if __name__=='__main__':
    App().mainloop()
