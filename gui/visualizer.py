"""
TreeVisualizer — interactive, draggable, zoomable ADTree renderer.

Renders the attack-defence tree on an embedded Matplotlib canvas with:
  - Hierarchical layout with glowing node borders
  - Attacker nodes: crimson  |  Defender nodes: forest-green
  - Labelled edges (action name) drawn mid-arc
  - Pan by left-drag on background, zoom by scroll wheel
  - Right-click context menu: Prune / Reset
  - Node drag: hold Ctrl + left-drag on a node to reposition it manually (Blitting High-Performance 60FPS)
  - Ultra-fast vectorized background grid
"""

import textwrap
import tkinter as tk
from typing import Any, Optional, Tuple
import importlib
import sys

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

# Force reload of palette module to avoid caching issues
if "gui.palette" in sys.modules:
    importlib.reload(sys.modules["gui.palette"])

from gui.palette import PALETTE

APP_BG = PALETTE.get("bg", "#0E1621")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _node_radius(label: str) -> float:
    n = len(label)
    if n <= 8:
        return 0.055
    if n <= 16:
        return 0.068
    return 0.085


def _get_color(key: str, default: str = None) -> str:
    if default is None:
        default = PALETTE.get("fallback_default", "#CCCCCC")
    return PALETTE.get(key, default)


# ─────────────────────────────────────────────────────────────────────────────
# TreeVisualizer
# ─────────────────────────────────────────────────────────────────────────────

class TreeVisualizer:
    def __init__(self, master_frame, on_prune=None, on_reset=None, on_edit=None):
        self.master_frame = master_frame
        self.on_prune = on_prune
        self.on_reset = on_reset
        self.on_edit = on_edit

        self.canvas: Optional[FigureCanvasTkAgg] = None
        self.fig: Optional[Figure] = None
        self.ax: Optional[Axes] = None

        self._G: Optional[Any] = None
        self._tree: Optional[Any] = None
        self._pos: dict[str, Tuple[float, float]] = {}
        self._role: dict[str, str] = {}

        self._drawn_nodes: dict = {}
        self._drawn_edges: dict = {}

        self._view_xlim: Optional[Tuple[float, float]] = None
        self._view_ylim: Optional[Tuple[float, float]] = None

        # Pan state
        self._pan_active = False
        self._pan_start_x = 0.0
        self._pan_start_y = 0.0
        self._pan_start_xlim: Optional[Tuple[float, float]] = None
        self._pan_start_ylim: Optional[Tuple[float, float]] = None

        # Node-drag state (Blitting variables)
        self._drag_node: Optional[str] = None
        self._ctrl_held = False
        self._bg_cache = None
        self._moving_artists = []

        self._context_menu = None

    # ── Public API ─────────────────────────────────────────────────────────

    def draw_tree(self, tree_obj) -> None:
        import traceback
        try:
            self._cleanup_canvas()

            self._tree = tree_obj
            G = tree_obj.to_graph()
            self._G = G

            self._role = {}
            for node in tree_obj.nodes:
                self._role[node.label] = node.role.strip() if node.role else "Attacker"

            root = tree_obj.root.label if tree_obj.root else next(iter(G.nodes))
            self._pos = self._hierarchical_pos(G, root)

            fig = Figure(figsize=(10, 6), dpi=100)
            ax = fig.add_subplot(111)
            self.fig = fig
            self.ax = ax

            fig.patch.set_facecolor(APP_BG)
            ax.set_facecolor(APP_BG)
            
            ax.set_aspect("equal")
            ax.axis("off")
            fig.subplots_adjust(left=0.0, right=1.0, top=1.0, bottom=0.0)

            self.canvas = FigureCanvasTkAgg(fig, master=self.master_frame)
            widget = self.canvas.get_tk_widget()
            widget.configure(bg=APP_BG, highlightthickness=0, bd=0)

            widget.pack(fill="both", expand=True)

            self._fit_view(reset=True)
            self._draw_all()
            self.canvas.draw()
            self._bind_events()

        except Exception as e:
            print(f"[DEBUG] TreeVisualizer.draw_tree error: {e}")
            traceback.print_exc()
            raise

    def cleanup(self) -> None:
        self._dismiss_menu()
        self._cleanup_canvas()
        self._pos = {}
        self._role = {}
        self._drawn_nodes.clear()
        self._drawn_edges.clear()
        self._G = None
        self._tree = None
        self._view_xlim = None
        self._view_ylim = None
        self._bg_cache = None
        self._moving_artists = []

    # ── Drawing ────────────────────────────────────────────────────────────

    def _draw_all(self) -> None:
        ax = self.ax
        fig = self.fig
        G = self._G

        if ax is None or fig is None or G is None or not self._pos:
            return

        current_xlim = self._view_xlim
        current_ylim = self._view_ylim

        ax.cla()
        self._drawn_nodes.clear()
        self._drawn_edges.clear()

        fig.patch.set_facecolor(APP_BG)
        ax.set_facecolor(APP_BG)
        ax.set_aspect("equal")
        ax.axis("off")
        fig.subplots_adjust(left=0.0, right=1.0, top=1.0, bottom=0.0)

        pos = self._pos
        role = self._role

        if current_xlim is None or current_ylim is None:
            self._fit_view(reset=True)
            current_xlim = self._view_xlim
            current_ylim = self._view_ylim

        if current_xlim is not None and current_ylim is not None:
            x_lo, x_hi = current_xlim
            y_lo, y_hi = current_ylim
        else:
            xs = [x for x, _ in pos.values()]
            ys = [y for _, y in pos.values()]
            x_lo, x_hi = min(xs) - 0.4, max(xs) + 0.4
            y_lo, y_hi = min(ys) - 0.4, max(ys) + 0.4

        # ─── GRID OPTIMIZING (VECTORIZED) ────────────────────────
        gx = np.arange(round(x_lo, 1), x_hi + 0.05, 0.1)
        gy = np.arange(round(y_lo, 1), y_hi + 0.05, 0.1)
        grid_color = _get_color("grid")
        
        X, Y = np.meshgrid(gx, gy)
        ax.plot(X.flatten(), Y.flatten(), marker=".", linestyle="none", color=grid_color, markersize=1, zorder=0, alpha=0.35)
        # ──────────────────────────────────────────────────────────────────────

        for u, v, data in G.edges(data=True):
            if u not in pos or v not in pos:
                continue

            x0, y0 = pos[u]
            x1, y1 = pos[v]

            target_role = role.get(v, "Attacker")
            color = _get_color("edge_dashed") if target_role == "Defender" else _get_color("edge_solid")
            lstyle = "--" if target_role == "Defender" else "-"

            ann = ax.annotate(
                "",
                xy=(x1, y1),
                xytext=(x0, y0),
                arrowprops=dict(
                    arrowstyle="-|>",
                    color=color,
                    lw=1.8,
                    linestyle=lstyle,
                    connectionstyle="arc3,rad=0.08",
                ),
                zorder=1,
                annotation_clip=False,
            )

            action = data.get("action", "")
            txt = None
            if action:
                mx = (x0 + x1) / 2 + 0.02
                my = (y0 + y1) / 2 + 0.02
                txt = ax.text(
                    mx, my, action,
                    fontsize=7,
                    color=_get_color("edge_label"),
                    ha="center", va="center", zorder=3,
                    bbox=dict(
                        boxstyle="round,pad=0.22",
                        facecolor=APP_BG,
                        edgecolor="none",
                        alpha=0.78,
                    ),
                    clip_on=False, 
                )
            
            self._drawn_edges[(u, v)] = {'arrow': ann, 'text': txt}

        for label, (x, y) in pos.items():
            r = _node_radius(label)
            is_def = role.get(label, "Attacker") == "Defender"

            fill_c = _get_color("defender") if is_def else _get_color("attacker")
            border_c = _get_color("defender_border") if is_def else _get_color("attacker_border")
            glow_c = _get_color("defender_glow") if is_def else _get_color("attacker_glow")

            glow1 = mpatches.Circle((x, y), r + 0.022, color=glow_c, alpha=0.14, zorder=2, clip_on=False)
            glow2 = mpatches.Circle((x, y), r + 0.010, color=glow_c, alpha=0.28, zorder=2, clip_on=False)
            fill = mpatches.Circle((x, y), r, color=fill_c, zorder=3, clip_on=False)
            border = mpatches.Circle((x, y), r, fill=False, edgecolor=border_c, linewidth=2.2, zorder=4, clip_on=False)

            ax.add_patch(glow1)
            ax.add_patch(glow2)
            ax.add_patch(fill)
            ax.add_patch(border)

            wrapped = "\n".join(textwrap.wrap(label, width=12))
            node_txt = ax.text(
                x, y, wrapped,
                fontsize=8, fontweight="bold",
                color=_get_color("node_text"),
                ha="center", va="center", zorder=5,
                multialignment="center",
                clip_on=False, 
            )

            self._drawn_nodes[label] = {
                'glow1': glow1, 'glow2': glow2, 'fill': fill, 'border': border, 'text': node_txt
            }

        att_patch = mpatches.Patch(color=_get_color("attacker"), label="Attacker")
        def_patch = mpatches.Patch(color=_get_color("defender"), label="Defender")
        ax.legend(
            handles=[att_patch, def_patch],
            loc="upper right",
            framealpha=0.35,
            facecolor=APP_BG,
            edgecolor=_get_color("edge_solid"),
            labelcolor=_get_color("node_text"),
            fontsize=9,
        )

        if current_xlim is not None and current_ylim is not None:
            ax.set_xlim(current_xlim)
            ax.set_ylim(current_ylim)

        if self.canvas is not None:
            self.canvas.draw_idle()

    def _fit_view(self, reset: bool = False) -> None:
        ax = self.ax
        if ax is None or not self._pos:
            return

        if not reset and self._view_xlim is not None and self._view_ylim is not None:
            ax.set_xlim(self._view_xlim)
            ax.set_ylim(self._view_ylim)
            return

        xs = [x for x, _ in self._pos.values()]
        ys = [y for _, y in self._pos.values()]

        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        dx = max(0.2, x_max - x_min)
        dy = max(0.2, y_max - y_min)

        pad_x = max(0.15, dx * 0.18)
        pad_y = max(0.15, dy * 0.18)

        if self.fig:
            fig_w, fig_h = self.fig.get_size_inches()
            aspect = fig_w / fig_h if fig_h > 0 else 1.0
            
            data_w = (x_max + pad_x) - (x_min - pad_x)
            data_h = (y_max + pad_y) - (y_min - pad_y)
            data_aspect = data_w / data_h if data_h > 0 else 1.0

            if data_aspect < aspect:
                extra_w = (data_h * aspect) - data_w
                self._view_xlim = (x_min - pad_x - extra_w/2, x_max + pad_x + extra_w/2)
                self._view_ylim = (y_min - pad_y, y_max + pad_y)
            else:
                extra_h = (data_w / aspect) - data_h
                self._view_xlim = (x_min - pad_x, x_max + pad_x)
                self._view_ylim = (y_min - pad_y - extra_h/2, y_max + pad_y + extra_h/2)
        else:
            self._view_xlim = (x_min - pad_x, x_max + pad_x)
            self._view_ylim = (y_min - pad_y, y_max + pad_y)

        ax.set_xlim(self._view_xlim)
        ax.set_ylim(self._view_ylim)

    def _hierarchical_pos(self, G, root, width=2.5, vert_gap=0.28, vert_loc=0.0, xcenter=0.5, pos=None, parent=None):
        if pos is None:
            pos = {}

        pos[root] = (xcenter, vert_loc)
        children = [n for n in G.neighbors(root) if n != parent]

        if children:
            min_w = 0.38
            dx = max(width / len(children), min_w)
            total_w = dx * len(children)
            nextx = xcenter - total_w / 2 + dx / 2

            for child in children:
                pos = self._hierarchical_pos(
                    G, child, width=dx * 0.95, vert_gap=vert_gap,
                    vert_loc=vert_loc - vert_gap, xcenter=nextx, pos=pos, parent=root
                )
                nextx += dx

        return pos

    def _bind_events(self) -> None:
        fig = self.fig
        if fig is None or self.canvas is None:
            return

        fc = fig.canvas
        fc.mpl_connect("scroll_event", self._on_scroll)
        fc.mpl_connect("button_press_event", self._on_press)
        fc.mpl_connect("button_release_event", self._on_release)
        fc.mpl_connect("motion_notify_event", self._on_motion)
        fc.mpl_connect("key_press_event", self._on_key_press)
        fc.mpl_connect("key_release_event", self._on_key_release)
        self.master_frame.bind("<Configure>", self._on_resize)

    def _on_resize(self, event) -> None:
        fig = self.fig
        if fig is None or self.canvas is None:
            return

        self.master_frame.update_idletasks()
        w = self.master_frame.winfo_width()
        h = self.master_frame.winfo_height()
        
        if w < 10 or h < 10:
            return

        dpi = fig.get_dpi()
        fig.set_size_inches(w / dpi, h / dpi, forward=False)
        fig.subplots_adjust(left=0.0, right=1.0, top=1.0, bottom=0.0)
        
        self._fit_view(reset=True)
        self.canvas.draw_idle()

    def _on_scroll(self, event) -> None:
        ax = self.ax
        if ax is None or event.inaxes != ax or event.xdata is None or event.ydata is None:
            return

        factor = (1 / 1.15) if event.button == "up" else 1.15
        xlim, ylim = ax.get_xlim(), ax.get_ylim()

        xlim_new = tuple(event.xdata + (x - event.xdata) * factor for x in xlim)
        ylim_new = tuple(event.ydata + (y - event.ydata) * factor for y in ylim)

        ax.set_xlim(xlim_new)
        ax.set_ylim(ylim_new)
        self._view_xlim = xlim_new
        self._view_ylim = ylim_new

        if self.canvas is not None:
            self.canvas.draw_idle()

    # ── Pan / Node-drag (BLITTING) ─────────────────────────────────────────

    def _on_press(self, event) -> None:
        ax = self.ax
        if ax is None:
            return

        if event.button == 1 and event.inaxes == ax:
            node = self._hit_node(event.xdata, event.ydata)
            if self._ctrl_held and node:
                self._drag_node = node
                self._moving_artists = []
                
                node_arts = self._drawn_nodes.get(node)
                if node_arts:
                    self._moving_artists.extend([
                        node_arts['glow1'], node_arts['glow2'], 
                        node_arts['fill'], node_arts['border'], node_arts['text']
                    ])
                
                for (u, v), edge_arts in self._drawn_edges.items():
                    if u == node or v == node:
                        self._moving_artists.append(edge_arts['arrow'])
                        if edge_arts['text']:
                            self._moving_artists.append(edge_arts['text'])
                
                for artist in self._moving_artists:
                    artist.set_animated(True)
                
                if self.canvas:
                    self.canvas.draw()
                    self._bg_cache = self.canvas.copy_from_bbox(self.ax.bbox)
                    
                    for artist in self._moving_artists:
                        self.ax.draw_artist(artist)
                    self.canvas.blit(self.ax.bbox)

            else:
                self._pan_active = True
                self._pan_start_x = event.x
                self._pan_start_y = event.y
                self._pan_start_xlim = ax.get_xlim()
                self._pan_start_ylim = ax.get_ylim()
        elif event.button == 3:
            self._show_context_menu(event)

    def _on_release(self, event) -> None:
        if event.button == 1:
            if self._drag_node:
                for artist in self._moving_artists:
                    artist.set_animated(False)
                
                self._drag_node = None
                self._moving_artists = []
                self._bg_cache = None
                
                if self.canvas:
                    self.canvas.draw_idle()
            else:
                self._pan_active = False

    def _on_motion(self, event) -> None:
        ax = self.ax
        if ax is None or event.inaxes != ax:
            return

        if self._drag_node and self._bg_cache is not None and event.xdata is not None and event.ydata is not None:
            nx, ny = event.xdata, event.ydata
            self._pos[self._drag_node] = (nx, ny)

            self.canvas.restore_region(self._bg_cache)

            node_arts = self._drawn_nodes.get(self._drag_node)
            if node_arts:
                node_arts['glow1'].set_center((nx, ny))
                node_arts['glow2'].set_center((nx, ny))
                node_arts['fill'].set_center((nx, ny))
                node_arts['border'].set_center((nx, ny))
                node_arts['text'].set_position((nx, ny))

            for (u, v), edge_arts in self._drawn_edges.items():
                if u == self._drag_node or v == self._drag_node:
                    x0, y0 = self._pos[u]
                    x1, y1 = self._pos[v]
                    
                    edge_arts['arrow'].xy = (x1, y1)
                    edge_arts['arrow'].set_position((x0, y0)) 
                    
                    if edge_arts['text']:
                        mx = (x0 + x1) / 2 + 0.02
                        my = (y0 + y1) / 2 + 0.02
                        edge_arts['text'].set_position((mx, my))

            for artist in self._moving_artists:
                self.ax.draw_artist(artist)

            self.canvas.blit(self.ax.bbox)
            return

        if self._pan_active and self._pan_start_xlim is not None and self._pan_start_ylim is not None:
            dx_pixels = event.x - self._pan_start_x
            dy_pixels = event.y - self._pan_start_y

            inv = ax.transData.inverted()
            x0, y0 = inv.transform((0, 0))
            x1, y1 = inv.transform((dx_pixels, dy_pixels))
            dx_data = x1 - x0
            dy_data = y1 - y0

            new_xlim = (self._pan_start_xlim[0] - dx_data, self._pan_start_xlim[1] - dx_data)
            new_ylim = (self._pan_start_ylim[0] - dy_data, self._pan_start_ylim[1] - dy_data)

            ax.set_xlim(new_xlim)
            ax.set_ylim(new_ylim)
            self._view_xlim = new_xlim
            self._view_ylim = new_ylim

            if self.canvas is not None:
                self.canvas.draw_idle()

    def _on_key_press(self, event) -> None:
        if event.key in ("control", "ctrl"):
            self._ctrl_held = True

    def _on_key_release(self, event) -> None:
        if event.key in ("control", "ctrl"):
            self._ctrl_held = False

    def _hit_node(self, xdata, ydata) -> Optional[str]:
        if xdata is None or ydata is None:
            return None

        best = None
        best_d = float("inf")

        for label, (nx_, ny_) in self._pos.items():
            r = _node_radius(label) + 0.02
            d = ((xdata - nx_) ** 2 + (ydata - ny_) ** 2) ** 0.5
            if d < best_d and d <= r:
                best_d = d
                best = label

        return best

    def _show_context_menu(self, event) -> None:
        if self.canvas is None or event.inaxes is None or not self._pos:
            return

        self._dismiss_menu()
        node_label = self._hit_node(event.xdata, event.ydata)

        menu = tk.Menu(
            self.master_frame, tearoff=0,
            bg=_get_color("menu_bg"), fg=_get_color("menu_fg"),
            activebackground=_get_color("menu_active_bg"), activeforeground=_get_color("menu_active_fg"),
            font=("Segoe UI", 11), bd=0, relief="flat"
        )

        if node_label:
            menu.add_command(label=f"\u270E  Edit Parameters: {node_label}", command=lambda: self._trigger_edit(node_label))
            menu.add_command(label=f"\u2702  Prune from: {node_label}", command=lambda: self._trigger_prune(node_label))
        else:
            menu.add_command(label="\u270E  Edit (click a node)", state="disabled")
            menu.add_command(label="\u2702  Prune (click a node)", state="disabled")

        menu.add_separator()
        menu.add_command(label="\u21ba  Reset tree", command=self._trigger_reset)

        self._context_menu = menu
        widget = self.canvas.get_tk_widget()
        root_x = widget.winfo_rootx() + int(event.x)
        root_y = widget.winfo_rooty() + int(widget.winfo_height() - event.y)
        menu.post(root_x, root_y)

    def _dismiss_menu(self) -> None:
        if self._context_menu:
            try:
                self._context_menu.destroy()
            except Exception:
                pass
        self._context_menu = None

    def _trigger_prune(self, label) -> None:
        if self.on_prune:
            self.on_prune(label)

    def _trigger_reset(self) -> None:
        if self.on_reset:
            self.on_reset()

    def _trigger_edit(self, label) -> None:
        if self.on_edit:
            self.on_edit(label)

    def _cleanup_canvas(self) -> None:
        self._dismiss_menu()

        if self.canvas:
            try:
                self.canvas.get_tk_widget().destroy()
            except Exception:
                pass

        if self.fig is not None:
            try:
                plt.close(self.fig)
            except Exception:
                pass

        self.canvas = None
        self.fig = None
        self.ax = None
        self._view_xlim = None
        self._view_ylim = None