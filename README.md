# Privacy Local LLM GUI

A cross-platform, privacy-focused desktop application that provides a graphical interface for interacting with local LLMs via [Ollama](https://ollama.com/). This tool automatically installs its dependencies, manages an Ollama server, pulls models on demand, and streams chat responses in real time.

---

![Screenshot of the UI](screenshot.png)


---

## Features

- 🚀 **Zero-touch dependency management**  
  Automatically detects missing Python packages (`ollama`, `langchain_ollama`, `tqdm`, `ttkthemes`, etc.), installs them with progress feedback, and restarts the app.

- 🖥️ **Built-in Ollama server management**  
  Checks if an Ollama server is running, starts it if needed, and gracefully shuts it down on exit.

- 📦 **On-the-fly model pulling**  
  Downloads models (`llama3.2:1b` by default, plus a curated list) with a progress bar and allows canceling or switching mid-download.

- 💬 **Interactive chat UI**  
  - System/human/assistant message history  
  - “Customer Service”, “Translator”, “Chat AI” roles out of the box  
  - Adjustable creativity (temperature) and reply length (max tokens) sliders  
  - Syntax-colored chat bubbles for user vs. assistant  
  - Light/Dark theme toggle  

- 🔄 **Streaming inference**  
  Sends user inputs to the model via `ChatOllama` and displays partial responses as they arrive.

---

## Requirements

- Python 3.8 or newer  
- [Ollama CLI](https://github.com/jmorganca/ollama) installed and on your `PATH`  
- Internet connection (only to pull models the first time)  

## Installation & Quick Start

1. Clone this repository:  
   ```bash
   git clone https://github.com/passimon/Privacy-Local-LLM-GUI.git
   cd Privacy-Local-LLM-GUI
   ```  
2. Make sure `python3` and `ollama` are on your PATH.  
3. Run the GUI:  
   ```bash
   ./gui.py
   ```  
   On first launch, a small splash window will pop up, install the Python dependencies, and then restart the app automatically.

---

## Usage

1. **Model Selector**  
   Choose from a list of preconfigured LLMs. Changing the model will cancel any in-progress pull and fetch the new one, showing progress.  
2. **Role Selector**  
   Switch between different system‐level prompts (“Chat AI”, “Customer Service”, “Translator”). Changing role resets the conversation history.  
3. **Creativity & Reply Length**  
   Adjust temperature (0.0–1.0) and max tokens (128–512) with sliders.  
4. **Chat Area**  
   ­– Type your prompt in the bottom entry and press **Enter** or **Send**.  
   ­– The assistant’s response streams in real time.  
5. **Theme Toggle**  
   Switch between dark (“equilux”) and light (“breeze”) themes.  
6. **Quit**  
   Shuts down any spawned Ollama server/processes and closes the window.

---

## Code Structure

- **Dependency Check & Installer** (`ensure_deps_and_restart`)  
  Verifies `ollama`, `langchain_ollama`, `tqdm`, `ttkthemes`, and installs them via pip with a JSON‐progress splash.  
- **Ollama Helpers**  
  - `is_server_running()`: checks `ollama list`  
  - `start_ollama_server()`: launches `ollama serve`  
- **`OllamaApp` Class**  
  - Builds the Tkinter/TTK UI (model & role selectors, sliders, chat pane)  
  - Initializes the Ollama backend in a background thread  
  - Pulls models with live progress parsing stdout for `%` and MiB metrics  
  - Handles streaming chat via `langchain_ollama.ChatOllama`  
  - Manages conversation history, UI updates, and cleanup  

---

## Customization

- **Add Models**  
  In the source, modify the `self.models` list.  
- **Define New Roles**  
  Extend the `self.roles` dict with a new key/value pair:  
  ```python
  self.roles["MyRole"] = "System prompt text for MyRole..."
  ```  
- **Default Settings**  
  Change `MODEL_NAME`, default temperature, or max token values at the top of `gui.py`.

---

## Troubleshooting

- **`ollama` not found**  
  Make sure you’ve installed Ollama and it’s on your `PATH`.  
- **Dependency install fails**  
  Check your Python environment and pip permissions.  
- **Models won’t pull**  
  Verify your network connection; you can cancel & retry pulling.

---

## License

This project is released under the MIT License.
