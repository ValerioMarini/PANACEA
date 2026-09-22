# PANACEA

**PANACEA** is a Python-based framework that reads an XML file exported from [ADTool](https://satoss.uni.lu/members/piotr/adtool/) and automatically generates a [PRISM-games](https://www.prismmodelchecker.org/games/) probabilistic model for formal security analysis. The framework supports multi-objective analysis (Cost and Time) via both a command-line interface and a fully-featured desktop GUI.

The project was tested on **Windows 11** and **Ubuntu WSL2** with the following software versions:
- [Python 3.12](https://www.python.org/downloads/release/python-3120/)
- [ADTool 2.2.2](https://satoss.uni.lu/members/piotr/adtool/)
- [PRISM-games 3.2.x](https://www.prismmodelchecker.org/games/)

***

## Table of Contents

- [Building (Executable)](#building-executable-file-linux---windows-compatible)
- [Installation (command line start only)](#installation-command-line-start-only)
  - [ADTool Setup](#adtool)
  - [PRISM-games Setup](#prism-games)
- [Command-Line Usage](#usage)
- [Graphical User Interface](#graphical-user-interface-terminal-start-version)
  - [First Run & Dependencies](#first-run--dependencies)
  - [Running the GUI](#running-the-gui)
  - [Sidebar Controls](#sidebar-controls)
  - [Home Tab](#home-tab--model-control-panel)
  - [Tree View Tab](#tree-view-tab)
  - [Statistics Tab (Analysis/Simulation)](#statistics-tab--analyssissimulation)

***

## Building (Executable file Linux - Windows compatible)

Automated builds for Windows and Linux are available in the **releases** tab. Pre-built executables are generated for each release, eliminating the need to install Python and dependencies manually. Check the [releases page](https://github.com/Mark8948/PANACEA/releases) on GitHub for the latest pre-built binaries for your platform.

***

## Installation (command line start only)

Clone the repository and install the required Python dependencies.

```bash
git clone https://github.com/Marini97/PANACEA.git
cd PANACEA
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### ADTool

You can create your attack-defense tree with ADTool. Once the tree is complete, export it as an XML file to use with PANACEA.

Follow these steps to set up and use ADTool:

1. Launch ADTool with:
   ```bash
   java -jar ADTool-2.2.2-full.jar
   ```

2. Create your attack-defense tree. Every node must have a **unique name** and a description containing the following fields:
   ```
   Type: Action/Attribute/Goal
   Action: if Type is Action then the action name
   Cost: if Type is Action then the cost of the action
   Time: if Type is Action then the time of the action
   Role: Attacker/Defender
   ```

3. Use the following as a reference for a correctly formatted node:
   ```
   Type: Action
   Action: exfiltrateData
   Cost: 50
   Time: 2
   Role: Attacker
   ```
   Some example XML tree files are also provided in the `trees/` folder of the repository.

4. Once the tree is complete, export it as an XML file to use with PANACEA.

***

### PRISM-games

PRISM-games is a **fundamental requirement** for PANACEA GUI to work correctly. Without it, the PRISM model generated from the Home tab cannot be executed, and the **Statistics tab will not function**. Install PRISM-games before using the GUI.


- **Windows**: double-click the shortcut created by the installer.
- **Linux/macOS GUI**: run `bin/xprism`.
- **Linux/macOS CLI**: run `bin/prism`.

***

## Usage

Run the conversion script `main.py` from the command line with the following arguments:

| Argument | Short | Description |
|---|---|---|
| `--input` | `-i` | Path to the XML file from ADTool |
| `--output` | `-o` | Path for the generated PRISM model output file |
| `--props` | | Generate the properties file for the PRISM model |
| `--prune` | `-p` | Name of the subtree root node to keep (prunes the rest) |
| `--time` | `-t` | Generate a time-based PRISM model (R-ADT variant) |

**Example — generate a time-based PRISM model:**

```bash
python main.py --input input.xml --output output.prism --time
```

**Example — run the generated model with PRISM-games:**

```bash
prism-games-3.2.1-linux64-x86/bin/prism \
    -javamaxmem 1g \
    -cuddmaxmem 1g \
    output.prism \
    properties.props -prop 1 \
    -exportresults output/results.csv:csv \
    -exportstrat output/strat.dot
```

> Adjust `-javamaxmem` and `-cuddmaxmem` according to your system RAM and the size of the model.

Alternatively, launch the PRISM-games GUI to load models interactively:

```bash
prism-games-3.2.1-linux64-x86/bin/xprism
```

***

## Graphical User Interface (Terminal start version)

PANACEA includes a full-featured **desktop GUI** built with [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) and Matplotlib. The interface is organized into three tabs — **Home**, **Tree View**, and **Statistics** — and supports interactive attack-defense tree visualization, node editing, pruning, and automated multi-objective (Cost + Time) simulation runs.

> **Note:** The GUI automatically applies the `--props` flag when generating a PRISM model; you do not need to specify it manually.

***

### First Run & Dependencies

Before launching the GUI, create and activate a virtual environment and install all dependencies.

**Windows:**

```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

**Linux / macOS:**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **Important:** Every time you open a new terminal session, re-activate the virtual environment with the second command (`activate`). Do **not** create a new `venv` — activate the existing one.

***

### Running the GUI

Once dependencies are installed and the venv is active, launch the GUI with:

```bash
python panacea-gui.py
```

The application window will open at a resolution of **1500×800** (minimum 1080×680). The interface features a dark theme with a sidebar on the left and a tabbed main area on the right.

***

### Sidebar Controls

The left sidebar is always visible and provides the core controls for loading files and configuring the export.

| Element | Description |
|---|---|
| **Import XML file** | Opens a file dialog to load an ADTool XML file. On Linux, it defaults to the Desktop folder; on Windows, to the home directory. |
| **Loaded file card** | Shows the name of the currently loaded XML file and its status badge (green = ready, red = no file loaded). |
| **Remove button** | Clears the currently loaded XML file and resets all analysis state. |
| **Export Options — Time Analysis (R-ADT)** | Checkbox that enables time-variant PRISM model generation when exporting from the Home tab. |

***

### Home Tab — Model Control Panel

The **Home** tab is the starting point for converting an XML tree into a PRISM model.

**Workflow:**

1. Load an XML file using the **Import XML file** button in the sidebar.
2. The status chip in the hero card updates to show the loaded filename and the **Generate PRISM model** button becomes active (turns green).
3. *(Optional)* Enable the **Time Analysis (R-ADT)** checkbox in the sidebar to generate a time-variant model.
4. Click **Generate PRISM model**. A save dialog opens — choose the output path and filename (`.prism` extension).
5. PANACEA generates the PRISM model and a companion `properties.props` file in the same directory, then automatically attempts to launch the PRISM-games engine.

**Output Console:**

The bottom section of the Home tab contains a scrollable console log that shows all events in real time — file loading, generation status, PRISM engine output, and errors. Use the **Clear log** button to reset it.

***

### Tree View Tab

The **Tree View** tab renders the loaded attack-defense tree as an interactive visual graph. This tab becomes populated as soon as a valid XML file is imported.

#### Navigation Controls

| Action | Effect |
|---|---|
| **Left Click + Drag** | Pan the view across the canvas |
| **Scroll Wheel** | Zoom in/out on the tree |
| **Ctrl + Left Click + Drag** | Move an individual node to reposition it in the layout |
| **Right Click on a node** | Open the context menu for node-level operations |

#### Context Menu (Right Click on a Node)

Right-clicking any node in the tree opens a context menu with the following actions:

- **Edit node** — Opens a modal dialog to modify the node's `Cost` and `Time` parameters. After saving, the change is tracked as a pending modification and the Statistics analysis button becomes available.
- **Prune subtree** — Removes all branches below the selected node, keeping only the subtree rooted at that node. The pruned view is displayed immediately. Subsequent prune operations can be chained.
- **Reset to original** — Discards all pruning applied in this session and restores the full original tree from the loaded XML.

#### Notes on Tree Editing

- Edits made in the Tree View tab (node cost/time changes and pruning) affect the model used for **Statistics analysis** and for the **PRISM model generation** from the Home tab. The currently displayed tree (pruned or full) is always used as the source.
- Each edit operation is logged in the Output Console with the changed values.
- The "Reset to original" action is also counted as a modification and will re-enable the Statistics analysis button.

***

### Statistics Tab — Analysis/Simulation

The **Statistics** tab provides automated **multi-objective dual analysis**: it runs PRISM-games twice in the background — once for **Attack Cost** and once for **Attack Time** — and plots the results on two synchronized charts to help visualize the security trade-off over multiple simulation runs.

#### How It Works

1. Load an XML file (sidebar) — the **Run Dual Analysis** button remains disabled until a tree is loaded.
2. *(Optional but recommended)* Use the **Tree View** tab to modify node parameters or prune the tree. Every modification flags the tree as "changed" and activates the analysis button.
3. Switch to the **Statistics** tab and click **Run Dual Analysis**.
4. The engine performs two sequential PRISM runs in the background:
   - **Step 1/2** — Cost model: generates a cost-variant PRISM model in a temporary folder and executes PRISM-games silently.
   - **Step 2/2** — Time model: generates a time-variant PRISM model in a temporary folder and executes PRISM-games silently.
5. Both results are parsed from the PRISM output (`Result: <value>`) and stored in the run history.
6. The plot updates automatically showing the evolution across all runs.

#### The Analysis Chart

The chart area is divided into two vertically stacked subplots that share the same x-axis (run index):

| Subplot | Color | Metric |
|---|---|---|
| **Top — Attack Cost Evolution** | Blue (`#3498DB`) | Minimum attacker cost computed by PRISM |
| **Bottom — Attack Time Evolution** | Red (`#E74C3C`) | Minimum attacker time computed by PRISM |

Each data point is annotated with its exact numeric value. The x-axis labels show the run number and the type of modification applied (e.g., `Run 1 (Base)`, `Run 2 (Edit: exfiltrateData)`, `Run 3 (2 changes)`).

#### Run Labels

| Condition | Label shown on chart |
|---|---|
| No pending modifications (initial load) | `Base` |
| One modification pending | Name of the modification (e.g., `Prune: rootNode`) |
| Multiple modifications pending | `N changes` (e.g., `3 changes`) |

#### Simulation Workflow Example

A typical simulation session to compare the impact of a defender countermeasure:

1. Import the base XML tree.
2. Go to **Statistics** → click **Run Dual Analysis** → this establishes the **baseline** (`Run 1 – Base`).
3. Go to **Tree View** → right-click a defender action node → **Edit node** → increase its cost.
4. Return to **Statistics** → click **Run Dual Analysis** → `Run 2 (Edit: <node>)` is added to the chart.
5. Compare the two data points: if the attacker's cost increased and/or time increased, the countermeasure is effective.
6. Repeat steps 3–5 to test additional scenarios. Each run adds a new point to the trend line.
7. Use **Reset Plot** to clear the history and start a new scenario from scratch.

> **Note:** If either PRISM run fails (engine not found, model error, parse error), the result is discarded and the analysis button re-enables so you can retry. Check the Output Console on the **Home** tab for detailed error messages.

#### Button States

| Button | Active when | Disabled when |
|---|---|---|
| **Run Dual Analysis** | A tree is loaded AND the tree has been modified since last run | No tree loaded, or no changes detected |
| **Reset Plot** | Always available once the tab is visible | — |


> **Note — PRISM-games auto-detection:** When the Statistics tab triggers an analysis run, the GUI automatically searches for the PRISM executable in the following order:
> - `C:\Program Files\prism-games-3.2.4\bin\prism.bat` (Windows priority)
> - `C:\Program Files\prism-games-3.2.2\bin\prism.bat` (Windows fallback)
> - System `PATH` environment variable
> - Common installation paths (`/usr/local/bin/prism`, `~/prism-games/bin/prism`, etc.)
>
> If the executable is not found automatically, a file dialog opens asking you to locate it manually. The path is remembered for the rest of the session.

***

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

***

*Made by [Mark8948](https://github.com/Mark8948) — 2026*