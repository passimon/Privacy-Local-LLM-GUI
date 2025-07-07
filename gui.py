#!/usr/bin/env python3
import sys
import subprocess
import os
import json
import threading
import time
import re
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

# We'll import these only if present; else our ensure_deps_and_restart
# will install them and re-exec.
try:
    from ttkthemes import ThemedTk
    from langchain_ollama import ChatOllama
except ImportError:
    ThemedTk = None
    ChatOllama = None

# 0) Declare your Python dependencies
PYTHON_DEPS = [
    "ollama==0.5.1",
    "langchain-ollama==0.3.3",
    "tqdm==4.67.1",
    "ttkthemes==2.0.1",
]

def ensure_deps_and_restart():
    """
    If any import fails, pop up a tiny splash window, install
    all dependencies with JSON progress, then re-exec ourselves.
    """
    try:
        import ollama, langchain_ollama, tqdm, ttkthemes
        return
    except ImportError:
        pass

    # Build splash
    splash = tk.Tk()
    splash.title("Installing dependencies…")
    splash.geometry("400x80")
    splash.resizable(False, False)

    lbl = ttk.Label(splash, text="Installing Python dependencies…")
    lbl.pack(pady=10)

    progress = ttk.Progressbar(
        splash, orient="horizontal", mode="determinate", maximum=100
    )
    progress.pack(fill="x", padx=20, pady=(0,10))

    splash.update_idletasks()

    # pip install command with JSON progress
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--disable-pip-version-check",
        "--progress-bar=json"
    ] + PYTHON_DEPS

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    def reader():
        for line in proc.stdout:
            line = line.strip()
            try:
                obj = json.loads(line)
                if "downloaded" in obj and "total" in obj:
                    pct = int((obj["downloaded"] / obj["total"]) * 100)
                    pct = max(0, min(100, pct))
                    splash.after(0, progress.configure, {"value": pct})
            except json.JSONDecodeError:
                pass
        proc.wait()
        splash.after(0, splash.destroy)

    threading.Thread(target=reader, daemon=True).start()
    splash.mainloop()

    if proc.returncode == 0:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    else:
        print("❌ Dependency installation failed.", file=sys.stderr)
        sys.exit(1)


# Call it at the very top
ensure_deps_and_restart()


# 1) Ollama helpers
MODEL_NAME     = "llama3.2:1b"
OLLAMA_LIST_CMD = ["ollama", "list"]

def is_server_running() -> bool:
    try:
        subprocess.run(
            OLLAMA_LIST_CMD,
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        return True
    except Exception:
        return False

def start_ollama_server():
    try:
        proc = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(2)
        if is_server_running():
            return proc
    except Exception:
        pass
    return None


# 2) GUI Application
class OllamaApp:
    def __init__(self, root: ThemedTk):
        self.root = root
        self.root.title("Privacy LLM Graphical User Interface")
        self.server_proc = None
        self.dark_theme = True

        # for cancelable pulls
        self.pull_cancel = None
        self.pull_proc   = None

        # Temperature & max_tokens
        self.temperature      = tk.DoubleVar(value=0.3)
        self.max_tokens       = tk.IntVar(value=256)
        self.temperature_str  = tk.StringVar()
        self.max_tokens_str   = tk.StringVar()
        self.temperature.trace_add("write", self._update_temperature_label)
        self.max_tokens.trace_add("write",   self._update_max_tokens_label)
        self._update_temperature_label()
        self._update_max_tokens_label()

        # Available models
        self.models = [
            "tinyllama:1.1b",
            "llama3.2:1b",
            "llama3.2:3b",
            "mistral:7b",
            "mistral-small:24b",
            "llama3.1:70b"
        ]
        self.model_var = tk.StringVar(value=MODEL_NAME)

        # Roles and prompts
        self.roles = {
            "Chat AI":
                "You are a highly versatile, friendly, and intelligent AI assistant. You listen carefully, ask clarifying questions when needed, and strive to deliver clear, concise, and contextually relevant answers. You adapt your tone and depth to the user’s needs. Begin each conversation with a warm greeting and an offer of help.\n\nExample Opening: “Hello! I’m here to help you with anything you need. What can I do for you today?”",
            "Customer Service":
                "You are a friendly, professional customer-service agent. You empathize with the user’s concerns, maintain a positive and polite tone, and work to resolve issues quickly and completely. If you need more information, you politely ask follow-up questions. Always close with an invitation to return if further help is needed.\n\nExample Opening: “Hi there! Thanks for reaching out to our support team. How can I assist you today?”",
            "Translator":
                "You are a precise and context-aware translator. You take text in one language and render it faithfully in another, preserving meaning, tone, and style. If a phrase is ambiguous, you ask for clarification before translating. When done, you confirm that the translation meets the user’s needs.\n\nExample Opening: “Sure—I’m ready to translate. Which language pair are we working with, and could you share the text you’d like translated?”",
            }
        self.role_var = tk.StringVar(value="Chat AI")

        # Initialize conversation history
        self.history = [
            ("system", self.roles[self.role_var.get()])
        ]

        self._build_ui()
        # Initialize backend on another thread
        threading.Thread(target=self._initialize_backend, daemon=True).start()

    # Slider Label Updates
    def _update_temperature_label(self, *args):
        val = round(self.temperature.get() * 10) / 10
        self.temperature_str.set(f"{val:.1f}")

    def _update_max_tokens_label(self, *args):
        val = self.max_tokens.get()
        self.max_tokens_str.set(f"{val}")

    def _snap_temperature(self, event):
        snapped = round(self.temperature.get() * 10) / 10
        snapped = min(max(snapped, 0.0), 1.0)
        self.temperature.set(snapped)

    # Build UI
    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(frm)
        top.pack(fill=tk.X, pady=(0,5))

        # Model selector
        ttk.Label(top, text="Model:").pack(side=tk.LEFT, padx=(0,2))
        cmb_model = ttk.Combobox(
            top,
            values=self.models,
            textvariable=self.model_var,
            state="readonly",
            width=16
        )
        cmb_model.pack(side=tk.LEFT)
        cmb_model.bind("<<ComboboxSelected>>", self._on_model_change)

        # Role selector
        ttk.Label(top, text="Role:").pack(side=tk.LEFT, padx=(10,2))
        cmb_role = ttk.Combobox(
            top,
            values=list(self.roles.keys()),
            textvariable=self.role_var,
            state="readonly",
            width=16
        )
        cmb_role.pack(side=tk.LEFT)
        cmb_role.bind("<<ComboboxSelected>>", self._on_role_change)

        # status + progress
        self.progress_label = ttk.Label(top, text="Initializing Ollama backend…")
        self.progress_label.pack(side=tk.LEFT, padx=(10,0))
        self.progress = ttk.Progressbar(top, mode="determinate", maximum=100)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Temperature slider
        ttk.Label(top, text="Creativity:").pack(side=tk.LEFT, padx=(10,2))
        temp_slider = ttk.Scale(
            top, from_=0.0, to=1.0,
            variable=self.temperature,
            orient=tk.HORIZONTAL, length=120
        )
        temp_slider.pack(side=tk.LEFT)
        temp_slider.bind("<ButtonRelease-1>", self._snap_temperature)
        ttk.Label(top, textvariable=self.temperature_str).pack(side=tk.LEFT, padx=(2,10))

        # Max Tokens slider
        ttk.Label(top, text="ReplyLength:").pack(side=tk.LEFT, padx=(0,2))
        tok_slider = ttk.Scale(
            top, from_=128, to=512,
            variable=self.max_tokens,
            orient=tk.HORIZONTAL, length=120
        )
        tok_slider.pack(side=tk.LEFT)
        ttk.Label(top, textvariable=self.max_tokens_str).pack(side=tk.LEFT, padx=(2,10))

        # Day/Night toggle
        self.toggle_btn = ttk.Button(
            top, text="Switch to Day", command=self._toggle_theme
        )
        self.toggle_btn.pack(side=tk.RIGHT)

        # Chat display
        self.txt = ScrolledText(
            frm, wrap=tk.WORD, state=tk.DISABLED,
            bg="#2E2E2E", fg="#E0E0E0", font=("Consolas", 11)
        )
        self.txt.pack(fill=tk.BOTH, expand=True)

        # Bottom entry + buttons
        bottom = ttk.Frame(frm)
        bottom.pack(fill=tk.X, pady=(10,0))

        self.entry = tk.Entry(
            bottom, bg="#2E2E2E", fg="white",
            insertbackground="white", font=("Consolas", 11)
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Return>", lambda e: self._on_send())

        self.btn_send = ttk.Button(
            bottom, text="Send", state=tk.DISABLED, command=self._on_send
        )
        self.btn_send.pack(side=tk.LEFT, padx=5)
        self.btn_quit = ttk.Button(bottom, text="Quit", command=self._on_quit)
        self.btn_quit.pack(side=tk.LEFT)

    # Role change resets history
    def _on_role_change(self, event=None):
        role = self.role_var.get()
        prompt = self.roles[role]
        self.history = [("system", prompt)]
        self._refresh_text()

    # Initialize Ollama server & pull default model
    def _initialize_backend(self):
        self._log("🔄 Starting Ollama server…")
        if not is_server_running():
            self.server_proc = start_ollama_server()
            if not self.server_proc:
                self._fatal("Could not start Ollama server.")
                return
        self._log("✅ Ollama server running.")

        self._log(f"🔄 Ensuring model {MODEL_NAME} is installed…")
        self.pull_cancel = threading.Event()
        self._pull_model(MODEL_NAME, self.pull_cancel)

        self.root.after(0, self.btn_send.config, {"state": tk.NORMAL})
        self._refresh_text()

    # When user picks a different model
    def _on_model_change(self, event=None):
        global MODEL_NAME
        if self.pull_cancel:
            self.pull_cancel.set()
        if self.pull_proc:
            try:
                self.pull_proc.terminate()
            except:
                pass

        MODEL_NAME = self.model_var.get()
        self.btn_send.config(state=tk.DISABLED)
        self.progress["value"] = 0
        self._log(f"🔄 Pulling model {MODEL_NAME} …")

        self.pull_cancel = threading.Event()
        threading.Thread(
            target=self._pull_model,
            args=(MODEL_NAME, self.pull_cancel),
            daemon=True
        ).start()

    # Core pull logic with stdout parsing
    def _pull_model(self, model_name: str, cancel_evt: threading.Event):
        pct_re  = re.compile(r"(\d+)%")
        mb_re   = re.compile(r"([\d.]+)\s*(?:M|Mi)B\s*/\s*([\d.]+)\s*(?:M|Mi)B")

        try:
            proc = subprocess.Popen(
                ["ollama", "pull", model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self.pull_proc = proc

            last_pct = 0
            last_done = None
            last_total = None

            for line in proc.stdout:
                if cancel_evt.is_set():
                    proc.terminate()
                    break

                line = line.strip()
                m_pct = pct_re.search(line)
                if m_pct:
                    last_pct = int(m_pct.group(1))
                m_mb = mb_re.search(line)
                if m_mb:
                    last_done  = float(m_mb.group(1))
                    last_total = float(m_mb.group(2))

                self.root.after(0, self._set_progress, last_pct, last_done, last_total)

            proc.wait()

            if cancel_evt.is_set():
                self.root.after(0, self._log, f"⚠️ Pull of {model_name} canceled.")
                return

            if proc.returncode == 0:
                self.root.after(0, self._log, f"✅ Model {model_name} ready.")
                self.root.after(0, self.btn_send.config, {"state": tk.NORMAL})
                self.root.after(0, self._set_progress, 100, None, None)
            else:
                raise RuntimeError("pull failed")

        except Exception as e:
            if not cancel_evt.is_set():
                msg = f"Failed to pull {model_name}.\n{e}"
                self.root.after(0, messagebox.showerror, "Error", msg)
                self.root.after(0, self._log, f"❌ Error pulling {model_name}.")
        finally:
            self.pull_proc = None

    # Sending user message
    def _on_send(self):
        msg = self.entry.get().strip()
        if not msg:
            return
        self.entry.delete(0, tk.END)
        self._append_history("human", msg)
        self._refresh_text()
        threading.Thread(target=self._call_llm, daemon=True).start()

    # Call the LLM with streaming responses
    def _call_llm(self):
        self.btn_send.config(state=tk.DISABLED)
        self._append_history("assistant", "")
        self._refresh_text()

        self.progress.config(mode="indeterminate")
        self.progress.start(50)

        llm = ChatOllama(
            model=MODEL_NAME,
            temperature=self.temperature.get(),
            num_predict=self.max_tokens.get()
        )

        full_reply = ""
        try:
            for chunk in llm.stream(self.history):
                full_reply += chunk.text()
        finally:
            self.progress.stop()
            self.progress.config(mode="determinate", value=0)

        self.history[-1] = ("assistant", full_reply)
        self._refresh_text()
        self.btn_send.config(state=tk.NORMAL)

    # History helpers
    def _append_history(self, role, txt):
        self.history.append((role, txt))

    def _refresh_text(self):
        self.txt.config(state=tk.NORMAL)
        self.txt.delete("1.0", tk.END)
        for role, msg in self.history:
            if role == "human":
                tag, pre = "user", "Customer: "
            elif role == "assistant":
                tag, pre = "assistant", "Agent: "
            else:
                tag, pre = "system", ""
            self.txt.insert(tk.END, pre + msg + "\n\n", tag)

        if self.dark_theme:
            self.txt.tag_config("user", foreground="white")
            self.txt.tag_config("assistant", foreground="white")
            self.txt.tag_config("system",
                                foreground="white",
                                font=("Consolas", 9, "italic"))
        else:
            self.txt.tag_config("user", foreground="blue")
            self.txt.tag_config("assistant", foreground="green")
            self.txt.tag_config("system",
                                foreground="gray30",
                                font=("Consolas", 9, "italic"))

        self.txt.see(tk.END)
        self.txt.config(state=tk.DISABLED)

    # Progress & logging
    def _set_progress(self, pct: int, done: float=None, total: float=None):
        self.progress["value"] = pct
        if done is not None and total is not None:
            self.progress_label.config(
                text=f"{pct}% — {done:.1f} MiB / {total:.1f} MiB"
            )
        else:
            self.progress_label.config(text=f"{pct}%")

    def _log(self, msg: str):
        self.progress_label.config(text=msg)

    def _fatal(self, msg: str):
        messagebox.showerror("Fatal error", msg)
        self._on_quit()

    # Theme toggle
    def _toggle_theme(self):
        self.dark_theme = not self.dark_theme
        theme = "equilux" if self.dark_theme else "breeze"
        self.root.set_theme(theme)

        if self.dark_theme:
            self.txt.config(bg="#2E2E2E", fg="#E0E0E0")
            self.entry.config(bg="#2E2E2E", fg="white", insertbackground="white")
            self.toggle_btn.config(text="Switch to Day")
        else:
            self.txt.config(bg="white", fg="black")
            self.entry.config(bg="white", fg="black", insertbackground="black")
            self.toggle_btn.config(text="Switch to Night")
        self._refresh_text()

    # Cleanup on quit
    def _on_quit(self):
        if self.server_proc:
            try:
                self.server_proc.terminate()
                self.server_proc.wait(timeout=3)
            except Exception:
                pass
        if self.pull_cancel:
            self.pull_cancel.set()
        if self.pull_proc:
            try:
                self.pull_proc.terminate()
            except:
                pass
        self.root.quit()


if __name__ == "__main__":
    root = ThemedTk(theme="equilux")
    app  = OllamaApp(root)
    root.mainloop()
