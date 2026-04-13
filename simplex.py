"""
Simplex Solver — Método Simplex + Gran M
GUI con tkinter. Ejecutar: python simplex_gran_m.py
Sin dependencias externas.
"""
import tkinter as tk
from tkinter import messagebox
from fractions import Fraction


# ──────────────────────────────────────────────
#  LÓGICA DEL SIMPLEX ESTÁNDAR (≤, variables de holgura)
# ──────────────────────────────────────────────
def resolver_simplex(c, A, b, tipo):
    n_vars = len(c)
    n_cons = len(A)
    total  = n_vars + n_cons
    all_names = [f"x{i+1}" for i in range(n_vars)] + \
                [f"s{i+1}" for i in range(n_cons)]

    T = []
    for i in range(n_cons):
        row = [Fraction(A[i][j]) for j in range(n_vars)] + \
              [Fraction(1) if j == i else Fraction(0) for j in range(n_cons)] + \
              [Fraction(b[i])]
        T.append(row)

    if tipo == "max":
        z_row = [-Fraction(ci) for ci in c] + [Fraction(0)] * n_cons + [Fraction(0)]
    else:
        z_row = [ Fraction(ci) for ci in c] + [Fraction(0)] * n_cons + [Fraction(0)]
    T.append(z_row)

    basis = list(range(n_vars, n_vars + n_cons))
    pasos = []

    def snap():
        return [list(row) for row in T], list(basis)

    t, b2 = snap()
    pasos.append(("Tabla inicial", t, b2, -1, -1))

    for iteracion in range(1, 51):
        pivot_col = -1
        min_val   = Fraction(-1, 1000000)
        for j in range(total):
            if T[n_cons][j] < min_val:
                min_val   = T[n_cons][j]
                pivot_col = j
        if pivot_col == -1:
            break

        pivot_row = -1
        min_ratio = None
        for i in range(n_cons):
            if T[i][pivot_col] > 0:
                ratio = T[i][-1] / T[i][pivot_col]
                if min_ratio is None or ratio < min_ratio:
                    min_ratio = ratio
                    pivot_row = i

        if pivot_row == -1:
            t, b2 = snap()
            pasos.append(("Problema no acotado", t, b2, pivot_col, -1))
            return None, None, pasos, "unbounded"

        pv = T[pivot_row][pivot_col]
        T[pivot_row] = [v / pv for v in T[pivot_row]]
        for i in range(n_cons + 1):
            if i != pivot_row:
                f = T[i][pivot_col]
                T[i] = [T[i][k] - f * T[pivot_row][k] for k in range(total + 1)]

        basis[pivot_row] = pivot_col
        t, b2 = snap()
        lbl = (f"Iteración {iteracion}  ·  "
               f"entra {all_names[pivot_col]}  /  "
               f"sale {all_names[b2[pivot_row]]}")
        pasos.append((lbl, t, b2, pivot_col, pivot_row))

    sol = {name: Fraction(0) for name in all_names}
    for i in range(n_cons):
        sol[all_names[basis[i]]] = T[i][-1]

    raw     = T[n_cons][-1]
    obj_val = -raw if tipo == "max" else raw
    return sol, obj_val, pasos, "ok"


# ──────────────────────────────────────────────
#  LÓGICA GRAN M
#  Soporta restricciones: <=, >=, =
# ──────────────────────────────────────────────
BIG_M = Fraction(10**6)   # M simbólica como fracción grande

def resolver_gran_m(c, A, b, tipos_res, tipo_obj):
    """
    c         : coeficientes función objetivo
    A         : matriz de restricciones (lista de listas)
    b         : RHS (lista)
    tipos_res : lista con "<=", ">=" o "=" por cada restricción
    tipo_obj  : "max" o "min"
    """
    n_vars = len(c)
    n_cons = len(A)

    # 1. Convertir todo a fracciones
    c = [Fraction(v) for v in c]
    A = [[Fraction(A[i][j]) for j in range(n_vars)] for i in range(n_cons)]
    b = [Fraction(v) for v in b]

    # 2. Construir variables auxiliares por restricción
    #    holgura (s): coef +1 para <=, -1 para >=
    #    artificial (a): coef +1 para >= y =
    slacks     = []   # (índice_columna, coef) por restricción (None si no hay)
    artificials= []   # (índice_columna) por restricción (None si no hay)

    col = n_vars
    for t in tipos_res:
        if t == "<=":
            slacks.append((col, Fraction(1)))
            artificials.append(None)
            col += 1
        elif t == ">=":
            slacks.append((col, Fraction(-1)))
            col += 1
            artificials.append(col)
            col += 1
        else:  # "="
            slacks.append(None)
            artificials.append(col)
            col += 1

    total_cols = col  # total variables (originales + holguras + artificiales)

    # Nombres de columnas
    slack_names = {}
    art_names   = {}
    s_idx = 1; a_idx = 1
    for i, t in enumerate(tipos_res):
        if slacks[i] is not None:
            slack_names[slacks[i][0]] = f"s{s_idx}"; s_idx += 1
        if artificials[i] is not None:
            art_names[artificials[i]] = f"a{a_idx}"; a_idx += 1

    all_names = ([f"x{i+1}" for i in range(n_vars)]
                 + [slack_names[k] for k in sorted(slack_names)]
                 + [art_names[k]   for k in sorted(art_names)])

    def col_name(j):
        if j < n_vars:               return f"x{j+1}"
        if j in slack_names:         return slack_names[j]
        if j in art_names:           return art_names[j]
        return f"v{j}"

    # 3. Construir tableau
    T = []
    for i in range(n_cons):
        row = [Fraction(0)] * (total_cols + 1)
        for j in range(n_vars):
            row[j] = A[i][j]
        if slacks[i] is not None:
            scol, scoef = slacks[i]
            row[scol] = scoef
        if artificials[i] is not None:
            row[artificials[i]] = Fraction(1)
        row[-1] = b[i]
        T.append(row)

    # 4. Fila Z
    # El tableau interno siempre trabaja como MIN (buscamos coeficientes negativos).
    # Para MAX: z_row[j] = -c[j]  →  penalización artificial = +M
    # Para MIN: z_row[j] = +c[j]  →  penalización artificial = +M
    # En ambos casos la penalización es +M porque el solver busca el más negativo
    # y queremos que las artificiales NUNCA sean columna pivote por sí solas.
    # La penalización correcta en la fila Z (forma estándar Min) es siempre +M.
    # PERO: para MAX la fila Z es -c, así que la penalización +M ya fuerza la
    # artificial fuera. Sin embargo, después de eliminar la artificial de la base
    # con el pivoteo inicial, los coeficientes deben quedar correctos.
    # El error real estaba en que para MAX se ponía +M pero la eliminación de
    # Gauss-Jordan sobre las filas de las artificiales en base no se hacía bien
    # cuando hay artificiales con excedente. Corregimos asegurándonos de que
    # la penalización sea consistente con la dirección de optimización:
    #   - Interno siempre Min  →  z_row artificiales = +M  (correcto)
    #   - Para Max se niega c pero la M sigue siendo +M    (correcto)
    z_row = [Fraction(0)] * (total_cols + 1)
    if tipo_obj == "max":
        for j in range(n_vars):
            z_row[j] = -c[j]
        M_pen = BIG_M      # +M penaliza en dirección correcta para Max interno
    else:
        for j in range(n_vars):
            z_row[j] = c[j]
        M_pen = BIG_M      # +M penaliza en dirección correcta para Min
    for i in range(n_cons):
        if artificials[i] is not None:
            z_row[artificials[i]] = M_pen

    T.append(z_row)

    # 5. Base inicial: variables de holgura (solo <=) y artificiales (>= y =)
    basis = []
    for i in range(n_cons):
        if artificials[i] is not None:
            basis.append(artificials[i])
        else:
            basis.append(slacks[i][0])

    # 6. Eliminar M de la fila Z para las artificiales que ya están en la base
    #    (hacer que las artificiales en la base tengan coef 0 en Z)
    for i in range(n_cons):
        if artificials[i] is not None:
            acol = artificials[i]
            factor = T[n_cons][acol]
            if factor != 0:
                T[n_cons] = [T[n_cons][k] - factor * T[i][k]
                             for k in range(total_cols + 1)]

    def snap():
        return [list(row) for row in T], list(basis)

    pasos = []
    t, b2 = snap()
    pasos.append(("Tabla inicial (Gran M)", t, b2, -1, -1))

    # 7. Iteraciones simplex
    for iteracion in range(1, 100):
        pivot_col = -1
        min_val   = Fraction(-1, 10**9)
        for j in range(total_cols):
            if T[n_cons][j] < min_val:
                min_val   = T[n_cons][j]
                pivot_col = j
        if pivot_col == -1:
            break

        pivot_row = -1
        min_ratio = None
        for i in range(n_cons):
            if T[i][pivot_col] > 0:
                ratio = T[i][-1] / T[i][pivot_col]
                if min_ratio is None or ratio < min_ratio:
                    min_ratio = ratio
                    pivot_row = i

        if pivot_row == -1:
            t, b2 = snap()
            pasos.append(("Problema no acotado", t, b2, pivot_col, -1))
            return None, None, pasos, "unbounded"

        pv = T[pivot_row][pivot_col]
        T[pivot_row] = [v / pv for v in T[pivot_row]]
        for i in range(n_cons + 1):
            if i != pivot_row:
                f = T[i][pivot_col]
                T[i] = [T[i][k] - f * T[pivot_row][k]
                        for k in range(total_cols + 1)]

        basis[pivot_row] = pivot_col
        t, b2 = snap()
        lbl = (f"Iteración {iteracion}  ·  "
               f"entra {col_name(pivot_col)}  /  "
               f"sale {col_name(b2[pivot_row])}")
        pasos.append((lbl, t, b2, pivot_col, pivot_row))

    # 8. Verificar factibilidad: alguna artificial aún en base con valor > 0?
    for i in range(n_cons):
        if basis[i] in art_names and T[i][-1] > Fraction(1, 10**6):
            t, b2 = snap()
            pasos.append(("Sin solución factible (artificial en base)", t, b2, -1, -1))
            return None, None, pasos, "infeasible"

    # 9. Extraer solución
    sol = {col_name(j): Fraction(0) for j in range(total_cols)}
    for i in range(n_cons):
        sol[col_name(basis[i])] = T[i][-1]

    raw     = T[n_cons][-1]
    obj_val = raw if tipo_obj == "max" else -raw  # MAX: raw=Z_opt; MIN: raw=-Z_opt

    return sol, obj_val, pasos, "ok"


def frac_str(f):
    """Convierte Fraction a string legible (maneja M grande mostrándola como M)."""
    if abs(f) >= BIG_M // 2:
        sign = "-" if f < 0 else ""
        return f"{sign}M"
    if f.denominator == 1:
        return str(f.numerator)
    return f"{f.numerator}/{f.denominator}"


# ──────────────────────────────────────────────
#  COLORES
# ──────────────────────────────────────────────
BG         = "#f5f6fa"
PANEL      = "#ffffff"
CARD       = "#f0f1f5"
BORDER     = "#d0d3de"
ACCENT     = "#4a6fa5"
ACCENT_M   = "#6b3fa0"   # púrpura para Gran M
ACCENT2    = "#2c7a5c"
TEXT       = "#2d2d2d"
TEXT_DIM   = "#6b7280"
PIVOT_ROW  = "#dbeafe"
PIVOT_COL  = "#dcfce7"
PIVOT_CELL = "#a7f3d0"
WARN       = "#92400e"
WARN_M     = "#5b21b6"   # color artificial
DANGER_BG  = "#fee2e2"
DANGER_FG  = "#991b1b"
SUCCESS_BG = "#d1fae5"
SUCCESS_FG = "#065f46"
INFO_BG    = "#ede9fe"
INFO_FG    = "#4c1d95"

FT  = ("Segoe UI", 16, "bold")
FH  = ("Segoe UI", 10, "bold")
FB  = ("Segoe UI", 10)
FM  = ("Courier New", 10)
FS  = ("Segoe UI",  9)
FBT = ("Segoe UI", 10, "bold")


# ──────────────────────────────────────────────
#  APP
# ──────────────────────────────────────────────
class SimplexApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simplex + Gran M Solver")
        self.configure(bg=BG)
        self.geometry("1200x820")
        self.minsize(960, 640)

        self.n_vars   = tk.IntVar(value=2)
        self.n_cons   = tk.IntVar(value=2)
        self.tipo     = tk.StringVar(value="max")
        self.metodo   = tk.StringVar(value="simplex")   # "simplex" | "gran_m"

        self.obj_entries   = []
        self.cons_entries  = []   # lista de (coefs, tipo_var, rhs_entry)
        self.pasos         = []
        self.paso_actual   = 0
        self.solucion      = None
        self.obj_val       = None
        self.estado        = None
        self.n_vars_sol    = 2
        self.tipo_sol      = "max"
        self.metodo_sol    = "simplex"
        self.col_names_sol = []

        self._build_ui()
        self._refresh_form()

    # ── CONSTRUCCIÓN DE UI ─────────────────────
    def _build_ui(self):
        hdr = tk.Frame(self, bg=ACCENT, padx=16, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Simplex + Gran M Solver", font=FT,
                 bg=ACCENT, fg="white").pack(side="left")
        tk.Label(hdr, text="  Resultados en fracción @Develenguas", font=FS,
                 bg=ACCENT, fg="#c8d8f0").pack(side="left")

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=10, pady=10)
        body.columnconfigure(0, weight=3, minsize=340)
        body.columnconfigure(1, weight=5)
        body.rowconfigure(0, weight=1)

        self.left  = tk.Frame(body, bg=PANEL, bd=1, relief="solid",
                              highlightbackground=BORDER, highlightthickness=1)
        self.right = tk.Frame(body, bg=BG)
        self.left.grid( row=0, column=0, sticky="nsew", padx=(0, 6))
        self.right.grid(row=0, column=1, sticky="nsew")

        self._build_left()
        self._build_right()

    def _build_left(self):
        p = tk.Frame(self.left, bg=PANEL, padx=14, pady=12)
        p.pack(fill="both", expand=True)

        # ── Método ──
        tk.Label(p, text="Método", font=FH, bg=PANEL, fg=TEXT_DIM).pack(anchor="w")
        mf = tk.Frame(p, bg=PANEL, pady=4)
        mf.pack(fill="x")
        for val, txt, col in [("simplex","Simplex estándar (solo ≤)", ACCENT),
                               ("gran_m", "Gran M  (≤, ≥, =)",        ACCENT_M)]:
            tk.Radiobutton(mf, text=txt, variable=self.metodo, value=val,
                           bg=PANEL, fg=col, selectcolor=col,
                           activebackground=PANEL, font=FB,
                           indicatoron=1, command=self._refresh_form).pack(anchor="w", pady=1)

        self._sep(p)

        # ── Configuración ──
        tk.Label(p, text="Configuración", font=FH, bg=PANEL, fg=TEXT_DIM).pack(anchor="w")
        cfg = tk.Frame(p, bg=PANEL, pady=4)
        cfg.pack(fill="x")

        tipo_f = tk.Frame(cfg, bg=PANEL)
        tipo_f.pack(side="left", padx=(0, 14))
        tk.Label(tipo_f, text="Optimizar", font=FS, bg=PANEL, fg=TEXT_DIM).pack(anchor="w")
        btns = tk.Frame(tipo_f, bg=PANEL)
        btns.pack()
        for val, txt in [("max","MAX"), ("min","MIN")]:
            tk.Radiobutton(btns, text=txt, variable=self.tipo, value=val,
                           bg=PANEL, fg=TEXT, selectcolor=ACCENT,
                           activebackground=PANEL, font=FB,
                           indicatoron=0, relief="groove", bd=1,
                           padx=8, pady=3, cursor="hand2").pack(side="left", padx=2)

        vf = tk.Frame(cfg, bg=PANEL)
        vf.pack(side="left", padx=(0, 10))
        tk.Label(vf, text="Variables", font=FS, bg=PANEL, fg=TEXT_DIM).pack(anchor="w")
        self._spinbox(vf, self.n_vars, 2, 6).pack()

        rf = tk.Frame(cfg, bg=PANEL)
        rf.pack(side="left")
        tk.Label(rf, text="Restricciones", font=FS, bg=PANEL, fg=TEXT_DIM).pack(anchor="w")
        self._spinbox(rf, self.n_cons, 1, 8).pack()

        self._sep(p)

        tk.Label(p, text="Función objetivo", font=FH, bg=PANEL, fg=TEXT_DIM).pack(anchor="w", pady=(4,2))
        self.obj_frame = tk.Frame(p, bg=PANEL)
        self.obj_frame.pack(fill="x")

        self._sep(p)

        self.cons_title = tk.Label(p, text="Restricciones", font=FH, bg=PANEL, fg=TEXT_DIM)
        self.cons_title.pack(anchor="w", pady=(0,2))
        self.cons_frame = tk.Frame(p, bg=PANEL)
        self.cons_frame.pack(fill="x")

        self._sep(p)

        btn_row = tk.Frame(p, bg=PANEL)
        btn_row.pack(fill="x")
        self._btn(btn_row, "⚡ Resolver",   self._resolver,       ACCENT,  "white").pack(side="left", padx=(0,6))
        self._btn(btn_row, "Ejemplo",        self._cargar_ejemplo, CARD,    TEXT   ).pack(side="left", padx=(0,4))
        self._btn(btn_row, "Limpiar",        self._limpiar,        CARD,    TEXT   ).pack(side="left")

        # Leyenda Gran M
        self.leyenda_m = tk.Label(p,
            text="ℹ  Gran M: variables artificiales (a) se penalizan con M=10⁶",
            font=FS, bg=INFO_BG, fg=INFO_FG, padx=6, pady=4, justify="left",
            wraplength=300)

    def _build_right(self):
        nav = tk.Frame(self.right, bg=PANEL, bd=1, relief="solid",
                       highlightbackground=BORDER, highlightthickness=1,
                       padx=10, pady=8)
        nav.pack(fill="x", pady=(0, 6))
        self._btn(nav, "◀ Anterior",  self._paso_ant, CARD, TEXT).pack(side="left", padx=(0,4))
        self._btn(nav, "Siguiente ▶", self._paso_sig, CARD, TEXT).pack(side="left")
        self.paso_lbl = tk.Label(nav, text="", font=FS, bg=PANEL, fg=TEXT_DIM)
        self.paso_lbl.pack(side="left", padx=10)

        self.result_frame = tk.Frame(self.right, bg=BG)
        self.result_frame.pack(fill="both", expand=True)
        self._mostrar_bienvenida()

    # ── FORMULARIO ─────────────────────────────
    def _refresh_form(self, *_):
        nv = self.n_vars.get()
        nc = self.n_cons.get()
        metodo = self.metodo.get()

        for w in self.obj_frame.winfo_children():  w.destroy()
        for w in self.cons_frame.winfo_children(): w.destroy()
        self.obj_entries  = []
        self.cons_entries = []

        # Título restricciones
        if metodo == "simplex":
            self.cons_title.config(text="Restricciones  (solo ≤)")
            self.leyenda_m.pack_forget()
        else:
            self.cons_title.config(text="Restricciones  (≤, ≥ o =)")
            self.leyenda_m.pack(fill="x", pady=(6,0))

        # Función objetivo
        rf = tk.Frame(self.obj_frame, bg=PANEL)
        rf.pack(fill="x")
        color_z = ACCENT_M if metodo == "gran_m" else ACCENT2
        tk.Label(rf, text="Z =", font=FB, bg=PANEL, fg=color_z, width=5).pack(side="left")
        for i in range(nv):
            if i > 0:
                tk.Label(rf, text="+", font=FB, bg=PANEL, fg=TEXT_DIM).pack(side="left", padx=2)
            e = self._entry(rf, width=5)
            e.pack(side="left")
            tk.Label(rf, text=f"x{i+1}", font=FB, bg=PANEL, fg=color_z).pack(side="left", padx=(1,4))
            self.obj_entries.append(e)

        # Restricciones
        for r in range(nc):
            rf2 = tk.Frame(self.cons_frame, bg=PANEL, pady=2)
            rf2.pack(fill="x")
            coefs = []
            for i in range(nv):
                if i > 0:
                    tk.Label(rf2, text="+", font=FB, bg=PANEL, fg=TEXT_DIM).pack(side="left", padx=2)
                e = self._entry(rf2, width=5)
                e.pack(side="left")
                tk.Label(rf2, text=f"x{i+1}", font=FB, bg=PANEL, fg=TEXT_DIM).pack(side="left", padx=(1,4))
                coefs.append(e)

            # Selector de tipo restricción
            tipo_var = tk.StringVar(value="<=")
            if metodo == "gran_m":
                sel = tk.OptionMenu(rf2, tipo_var, "<=", ">=", "=")
                sel.config(font=FB, bg=CARD, fg=WARN_M, relief="solid",
                           bd=1, width=3, cursor="hand2")
                sel.pack(side="left", padx=4)
            else:
                tk.Label(rf2, text="≤", font=FB, bg=PANEL, fg=WARN).pack(side="left", padx=4)

            rhs = self._entry(rf2, width=6)
            rhs.pack(side="left")
            self.cons_entries.append((coefs, tipo_var, rhs))

    # ── RESOLVER ───────────────────────────────
    def _resolver(self):
        try:
            c = []
            for e in self.obj_entries:
                v = e.get().strip()
                c.append(Fraction(v) if v not in ("", "-") else Fraction(0))
        except Exception:
            messagebox.showerror("Error", "Coeficiente de objetivo inválido."); return

        try:
            A, b_vals, tipos_res = [], [], []
            for (coefs, tipo_var, rhs_e) in self.cons_entries:
                row = []
                for e in coefs:
                    v = e.get().strip()
                    row.append(Fraction(v) if v not in ("", "-") else Fraction(0))
                A.append(row)
                v = rhs_e.get().strip()
                b_vals.append(Fraction(v) if v not in ("", "-") else Fraction(0))
                tipos_res.append(tipo_var.get())
        except Exception:
            messagebox.showerror("Error", "Coeficiente de restricción inválido."); return

        metodo = self.metodo.get()

        if metodo == "simplex":
            # Solo permite <=; verificar RHS >= 0
            if any(v < 0 for v in b_vals):
                messagebox.showerror("Error",
                    "Los RHS deben ser ≥ 0 para el método Simplex estándar.\n"
                    "Usa el método Gran M para más flexibilidad."); return
            solucion, obj_val, pasos, estado = resolver_simplex(
                c, A, b_vals, self.tipo.get())
            col_names = ([f"x{i+1}" for i in range(len(c))]
                         + [f"s{i+1}" for i in range(len(A))])
        else:
            # Gran M: manejar RHS negativo multiplicando fila por -1 e invirtiendo tipo
            for i in range(len(b_vals)):
                if b_vals[i] < 0:
                    b_vals[i] = -b_vals[i]
                    A[i] = [-x for x in A[i]]
                    tipos_res[i] = ">=" if tipos_res[i] == "<=" else "<=" if tipos_res[i] == ">=" else "="
            solucion, obj_val, pasos, estado = resolver_gran_m(
                c, A, b_vals, tipos_res, self.tipo.get())
            # col_names se construyen dentro de la función; tomamos de pasos si hay
            col_names = []

        self.pasos        = pasos
        self.solucion     = solucion
        self.obj_val      = obj_val
        self.estado       = estado
        self.n_vars_sol   = len(c)
        self.tipo_sol     = self.tipo.get()
        self.metodo_sol   = metodo
        self.col_names_sol= col_names
        self.paso_actual  = 0
        self._mostrar_paso()

    # ── NAVEGACIÓN ─────────────────────────────
    def _paso_ant(self):
        if self.paso_actual > 0:
            self.paso_actual -= 1; self._mostrar_paso()

    def _paso_sig(self):
        if self.paso_actual < len(self.pasos) - 1:
            self.paso_actual += 1; self._mostrar_paso()

    # ── MOSTRAR PASO ───────────────────────────
    def _mostrar_paso(self):
        for w in self.result_frame.winfo_children(): w.destroy()
        if not self.pasos: return

        label, T, basis, pcol, prow = self.pasos[self.paso_actual]
        n_cons     = len(basis)
        total_vars = len(T[0]) - 1   # excluye RHS

        # Reconstruir nombres desde el tamaño del tableau
        n_vars = self.n_vars_sol
        n_slack = 0; n_art = 0
        # Contar tipos para deducir nombres
        if self.metodo_sol == "gran_m":
            n_extra = total_vars - n_vars
            # Reconstruir desde pasos: usar info del label si está disponible
            # Mejor: rederivamos nombres desde el total de columnas y restricciones
            # La función gran_m genera: x1..xN, s1..sS, a1..aA
            # No tenemos la cuenta exacta aquí, usamos etiquetas genéricas
            all_names = _infer_names(n_vars, total_vars, n_cons,
                                     self.pasos, basis, T)
        else:
            all_names = ([f"x{i+1}" for i in range(n_vars)]
                         + [f"s{i+1}" for i in range(n_cons)])

        self.paso_lbl.config(text=f"Paso {self.paso_actual+1} / {len(self.pasos)}")

        # Header de paso
        acc = ACCENT_M if self.metodo_sol == "gran_m" else ACCENT
        lbl_frame = tk.Frame(self.result_frame, bg=acc, padx=10, pady=6)
        lbl_frame.pack(fill="x", pady=(0, 6))
        tk.Label(lbl_frame, text=label, font=FH, bg=acc, fg="white").pack(anchor="w")

        # Scrollable tableau
        outer  = tk.Frame(self.result_frame, bg=BG)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vsb = tk.Scrollbar(outer, orient="vertical",   command=canvas.yview)
        hsb = tk.Scrollbar(outer, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right",  fill="y")
        hsb.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=BG, padx=8, pady=6)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        CW = 10

        headers = ["Base"] + all_names + ["RHS"]
        for j, h in enumerate(headers):
            is_pc = (0 < j <= total_vars) and (j - 1 == pcol)
            is_art = (j > 0) and (j - 1 < len(all_names)) and all_names[j-1].startswith("a")
            bg = PIVOT_COL if is_pc else (INFO_BG if is_art else CARD)
            fg = ACCENT2   if is_pc else (INFO_FG if is_art else acc)
            tk.Label(inner, text=h, font=FH, bg=bg, fg=fg,
                     width=CW, padx=4, pady=5,
                     relief="solid", bd=1).grid(row=0, column=j, padx=1, pady=1)

        for r in range(n_cons):
            is_pr     = (r == prow)
            base_name = all_names[basis[r]] if basis[r] < len(all_names) else "?"
            is_art_base = base_name.startswith("a")
            row_bg    = PIVOT_ROW if is_pr else (INFO_BG if is_art_base else PANEL)
            tk.Label(inner, text=base_name, font=FH,
                     bg=row_bg, fg=INFO_FG if is_art_base else acc,
                     width=CW, padx=4, pady=4,
                     relief="solid", bd=1).grid(row=r+1, column=0, padx=1, pady=1)
            for j in range(total_vars):
                val   = T[r][j]
                is_pc = (j == pcol)
                if   is_pr and is_pc: cbg, cfg2 = PIVOT_CELL, SUCCESS_FG
                elif is_pr:           cbg, cfg2 = PIVOT_ROW,  TEXT
                elif is_pc:           cbg, cfg2 = PIVOT_COL,  ACCENT2
                else:                 cbg, cfg2 = PANEL,      TEXT
                txt = "0" if val == 0 else frac_str(val)
                tk.Label(inner, text=txt, font=FM, bg=cbg, fg=cfg2,
                         width=CW, padx=4, pady=4,
                         relief="solid", bd=1).grid(row=r+1, column=j+1, padx=1, pady=1)
            rhs_val = T[r][-1]
            txt = "0" if rhs_val == 0 else frac_str(rhs_val)
            tk.Label(inner, text=txt, font=FM,
                     bg=PIVOT_ROW if is_pr else PANEL,
                     fg=SUCCESS_FG if is_pr else TEXT,
                     width=CW, padx=4, pady=4,
                     relief="solid", bd=1).grid(row=r+1, column=total_vars+1, padx=1, pady=1)

        # Fila Z
        zr = T[n_cons]
        z_color = WARN_M if self.metodo_sol == "gran_m" else WARN
        tk.Label(inner, text="Z", font=FH, bg=CARD, fg=z_color,
                 width=CW, padx=4, pady=5,
                 relief="solid", bd=1).grid(row=n_cons+1, column=0, padx=1, pady=1)
        for j in range(total_vars):
            val = zr[j]
            txt = "0" if val == 0 else frac_str(val)
            tk.Label(inner, text=txt, font=FM, bg=CARD, fg=z_color,
                     width=CW, padx=4, pady=5,
                     relief="solid", bd=1).grid(row=n_cons+1, column=j+1, padx=1, pady=1)
        zrhs = zr[-1]
        txt  = "0" if zrhs == 0 else frac_str(zrhs)
        tk.Label(inner, text=txt, font=FH, bg=CARD, fg=z_color,
                 width=CW, padx=4, pady=5,
                 relief="solid", bd=1).grid(row=n_cons+1, column=total_vars+1, padx=1, pady=1)

        # Leyenda colores
        if pcol >= 0 and prow >= 0:
            ley = tk.Frame(self.result_frame, bg=BG)
            ley.pack(anchor="w", padx=10, pady=4)
            items = [(PIVOT_CELL, SUCCESS_FG, "Celda pivote"),
                     (PIVOT_ROW,  TEXT,       "Fila pivote"),
                     (PIVOT_COL,  ACCENT2,    "Columna pivote")]
            if self.metodo_sol == "gran_m":
                items.append((INFO_BG, INFO_FG, "Variable artificial"))
            for bgc, fgc, txt in items:
                f = tk.Frame(ley, bg=BG); f.pack(side="left", padx=6)
                tk.Label(f, text="   ", bg=bgc, relief="solid", bd=1).pack(side="left")
                tk.Label(f, text=txt, font=FS, bg=BG, fg=TEXT_DIM).pack(side="left", padx=3)

        # Resultado final
        is_last = (self.paso_actual == len(self.pasos) - 1)
        if is_last:
            if self.estado == "ok" and self.solucion is not None:
                self._mostrar_solucion()
            elif self.estado == "unbounded":
                box = tk.Frame(self.result_frame, bg=DANGER_BG, padx=12, pady=8)
                box.pack(fill="x", padx=10, pady=8)
                tk.Label(box, text="⚠  Problema no acotado (unbounded)",
                         font=FH, bg=DANGER_BG, fg=DANGER_FG).pack(anchor="w")
            elif self.estado == "infeasible":
                box = tk.Frame(self.result_frame, bg=DANGER_BG, padx=12, pady=8)
                box.pack(fill="x", padx=10, pady=8)
                tk.Label(box, text="⚠  Sin solución factible (infeasible)",
                         font=FH, bg=DANGER_BG, fg=DANGER_FG).pack(anchor="w")
                tk.Label(box,
                    text="Una variable artificial permanece en la base con valor > 0.\n"
                         "El sistema de restricciones no tiene solución.",
                    font=FS, bg=DANGER_BG, fg=DANGER_FG).pack(anchor="w")

    def _mostrar_solucion(self):
        box = tk.Frame(self.result_frame, bg=SUCCESS_BG, padx=14, pady=10)
        box.pack(fill="x", padx=10, pady=8)
        tk.Label(box, text="✓  Solución óptima", font=FH,
                 bg=SUCCESS_BG, fg=SUCCESS_FG).pack(anchor="w", pady=(0, 6))
        vf = tk.Frame(box, bg=SUCCESS_BG)
        vf.pack(fill="x")
        for i in range(self.n_vars_sol):
            name = f"x{i+1}"
            val  = self.solucion.get(name, Fraction(0))
            col  = tk.Frame(vf, bg=SUCCESS_BG, padx=10); col.pack(side="left")
            tk.Label(col, text=name, font=FS, bg=SUCCESS_BG, fg=TEXT_DIM).pack()
            tk.Label(col, text=frac_str(val),
                     font=("Segoe UI", 15, "bold"), bg=SUCCESS_BG, fg=TEXT).pack()
        tk.Frame(box, bg=BORDER, height=1).pack(fill="x", pady=6)
        tipo_str = "Máximo" if self.tipo_sol == "max" else "Mínimo"
        tk.Label(box,
                 text=f"Z {tipo_str} = {frac_str(self.obj_val)}",
                 font=("Segoe UI", 14, "bold"), bg=SUCCESS_BG, fg=SUCCESS_FG).pack(anchor="w")
        if self.metodo_sol == "gran_m":
            tk.Label(box,
                     text="(Método Gran M  ·  variables artificiales excluidas del resultado)",
                     font=FS, bg=SUCCESS_BG, fg=TEXT_DIM).pack(anchor="w")

    def _mostrar_bienvenida(self):
        for w in self.result_frame.winfo_children(): w.destroy()
        f = tk.Frame(self.result_frame, bg=BG)
        f.pack(expand=True)
        tk.Label(f, text="📊", font=("Segoe UI", 40), bg=BG).pack(pady=(60, 8))
        tk.Label(f, text="Configura el problema y presiona  ⚡ Resolver",
                 font=FB, bg=BG, fg=TEXT_DIM).pack()
        tk.Label(f, text='Usa "Gran M" para restricciones ≥ o = ',
                 font=FS, bg=BG, fg=BORDER).pack(pady=4)

    # ── EJEMPLOS ───────────────────────────────
    def _cargar_ejemplo(self):
        if self.metodo.get() == "simplex":
            # Ejemplo clásico MAX 5x1+4x2 s.t. 6x1+4x2<=24, x1+2x2<=6, -x1+x2<=1
            self.n_vars.set(2); self.n_cons.set(3); self.tipo.set("max")
            self._refresh_form()
            for e, v in zip(self.obj_entries, [5, 4]):
                e.delete(0, tk.END); e.insert(0, str(v))
            datos = [([6, 4], "<=", 24), ([1, 2], "<=", 6), ([-1, 1], "<=", 1)]
            for (coefs, tipo_var, rhs_e), (av, tv, bv) in zip(self.cons_entries, datos):
                for e, v in zip(coefs, av): e.delete(0, tk.END); e.insert(0, str(v))
                rhs_e.delete(0, tk.END); rhs_e.insert(0, str(bv))
        else:
            # Ejemplo Gran M: MIN x1+2x2 s.t. x1+x2>=4, x1+3x2>=6
            self.n_vars.set(2); self.n_cons.set(2); self.tipo.set("min")
            self._refresh_form()
            for e, v in zip(self.obj_entries, [1, 2]):
                e.delete(0, tk.END); e.insert(0, str(v))
            datos = [([1, 1], ">=", 4), ([1, 3], ">=", 6)]
            for (coefs, tipo_var, rhs_e), (av, tv, bv) in zip(self.cons_entries, datos):
                for e, v in zip(coefs, av): e.delete(0, tk.END); e.insert(0, str(v))
                tipo_var.set(tv)
                rhs_e.delete(0, tk.END); rhs_e.insert(0, str(bv))

    def _limpiar(self):
        for e in self.obj_entries:
            e.delete(0, tk.END); e.insert(0, "0")
        for coefs, tipo_var, rhs in self.cons_entries:
            for e in coefs: e.delete(0, tk.END); e.insert(0, "0")
            tipo_var.set("<=")
            rhs.delete(0, tk.END); rhs.insert(0, "0")
        self.pasos = []; self.paso_lbl.config(text="")
        self._mostrar_bienvenida()

    # ── WIDGETS HELPERS ────────────────────────
    def _entry(self, parent, width=6):
        e = tk.Entry(parent, width=width, font=FM,
                     bg=CARD, fg=TEXT, insertbackground=TEXT,
                     relief="solid", bd=1)
        e.insert(0, "0")
        return e

    def _spinbox(self, parent, var, from_, to):
        return tk.Spinbox(parent, from_=from_, to=to, textvariable=var,
                          width=5, font=FB, bg=CARD, fg=TEXT,
                          relief="solid", bd=1,
                          command=self._refresh_form)

    def _btn(self, parent, text, cmd, bg, fg=TEXT):
        return tk.Button(parent, text=text, command=cmd,
                         font=FBT, bg=bg, fg=fg, relief="flat", bd=0,
                         padx=10, pady=5, cursor="hand2",
                         activebackground=ACCENT, activeforeground="white")

    def _sep(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=8)


# ──────────────────────────────────────────────
#  HELPER: inferir nombres de columnas desde tableau
# ──────────────────────────────────────────────
def _infer_names(n_vars, total_vars, n_cons, pasos, basis, T):
    """
    Intenta reconstruir nombres de columnas a partir de la información disponible.
    Para Gran M, las variables artificiales tienen coeficientes muy grandes en Z.
    """
    # Buscar en el label del primer paso
    first_label = pasos[0][0] if pasos else ""
    # Determinar artificiales: columnas cuyo valor en fila Z inicial es ~ BIG_M
    z_row_init = pasos[0][1][n_cons]  # fila Z del tableau inicial
    threshold  = BIG_M // 2

    art_cols = set()
    for j, v in enumerate(z_row_init[:-1]):
        if abs(v) >= threshold:
            art_cols.add(j)

    # Columnas que no son originales ni artificiales => holguras/excedentes
    names = []
    s_idx = 1; a_idx = 1
    for j in range(total_vars):
        if j < n_vars:
            names.append(f"x{j+1}")
        elif j in art_cols:
            names.append(f"a{a_idx}"); a_idx += 1
        else:
            names.append(f"s{s_idx}"); s_idx += 1
    return names


if __name__ == "__main__":
    app = SimplexApp()
    app.mainloop()