from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure


class PlotPanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.figure = Figure(figsize=(9, 5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side="bottom", fill="x")
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

    def reset(self):
        self.figure.clear()
        self.toolbar.update()
        return self.figure.add_subplot(111)

    def draw(self):
        self.figure.tight_layout(pad=1.6)
        self.canvas.draw_idle()

    def destroy(self):
        for attr in ("_idle_draw_id", "_event_loop_id"):
            callback = getattr(self.canvas, attr, None)
            if callback is not None:
                self.canvas.get_tk_widget().after_cancel(callback)
                setattr(self.canvas, attr, None)
        self.figure.clear()
        super().destroy()
