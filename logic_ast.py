import re
import itertools
from typing import List, Set, Dict, Union, Optional

# ========== AST (abstract syntax tree) структуры ==========

class Node: pass

class Var(Node):
    def __init__(self, name: str):
        self.name = name
    def __repr__(self): return self.name

class Const(Node):
    def __init__(self, name: str):
        self.name = name
    def __repr__(self): return self.name

class Function(Node):
    """Терм — функция (используется для сколемовых функций)."""
    def __init__(self, name: str, args: List[Node]):
        self.name = name
        self.args = args
    def __repr__(self):
        if self.args:
            return f"{self.name}({','.join(map(str,self.args))})"
        return self.name

class Predicate(Node):
    def __init__(self, name: str, args: List[Node]):
        self.name = name
        self.args = args
    def __repr__(self): return "%s(%s)" % (self.name, ",".join(map(str, self.args)))

class Not(Node):
    def __init__(self, child: Node):
        self.child = child
    def __repr__(self): return f"¬{self.child}"

class And(Node):
    def __init__(self, children: List[Node]):
        self.children = children
    def __repr__(self): return "(" + " ∧ ".join(map(str, self.children)) + ")"

class Or(Node):
    def __init__(self, children: List[Node]):
        self.children = children
    def __repr__(self): return "(" + " ∨ ".join(map(str, self.children)) + ")"

class Implies(Node):
    def __init__(self, left: Node, right: Node):
        self.left = left
        self.right = right
    def __repr__(self): return f"({self.left} → {self.right})"

class ForAll(Node):
    def __init__(self, var: str, body: Node):
        self.var = var
        self.body = body
    def __repr__(self): return f"(∀{self.var} {self.body})"

class Exists(Node):
    def __init__(self, var: str, body: Node):
        self.var = var
        self.body = body
    def __repr__(self): return f"(∃{self.var} {self.body})"


# ========== Парсер строк формул ("¬Человек(x) ∨ Смертен(x)") → AST ==========

def parse_formula(s: str) -> Node:
    s = s.replace(" ", "")

    def parse_atom(atom):
        atom = atom.strip()
        # Стандарт: Имя(арг1, ...)
        m = re.match(r'^([A-Za-zА-Яа-яёЁ0-9_]+)\((.*)\)$', atom)
        if m:
            name = m.group(1)
            rest = m.group(2)
            args = []
            if rest.strip() == "":
                # ноль аргументов
                return Predicate(name, [])
            parts = []
            depth = 0
            cur = ""
            for ch in rest:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                if ch == "," and depth == 0:
                    parts.append(cur)
                    cur = ""
                else:
                    cur += ch
            if cur:
                parts.append(cur)
            for part in parts:
                part = part.strip()
                # Оставляем буквы и цифры/подчёркивания внутри имени переменной/константы
                part = re.sub(r'[^A-Za-zА-Яа-яёЁ0-9_]', '', part)
                if not part:
                    continue
                if part[0].isupper():
                    args.append(Const(part))
                else:
                    args.append(Var(part))
            return Predicate(name, args)
        # Обычная атомарная строка без скобок — воспринимаем как предикат без аргументов
        atom_no_parens = re.sub(r'[\(\)]', '', atom)
        atom_no_parens = re.sub(r'[^A-Za-zА-Яа-яёЁ0-9_]', '', atom_no_parens)
        return Predicate(atom_no_parens, [])

    # Снимаем внешние скобки (только один уровень)
    if s.startswith("(") and s.endswith(")"):
        # проверим совпадает ли скобочная пара (баланс)
        depth = 0
        balanced = True
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth == 0 and i < len(s)-1:
                balanced = False
                break
        if balanced:
            s = s[1:-1]

    # Кванторы: допускаем латинские и русские имена переменных (берём последовательность букв/цифр после квантора)
    m = re.match(r'∀([A-Za-z0-9_]+)\((.+)\)$', s)
    if m:
        return ForAll(m.group(1), parse_formula(m.group(2)))
    m = re.match(r'∃([A-Za-z0-9_]+)\((.+)\)$', s)
    if m:
        return Exists(m.group(1), parse_formula(m.group(2)))

    # Импликация — разбиваем только на верхнем уровне
    if "→" in s:
        parts = []
        depth = 0
        curr = ""
        found = False
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "→" and depth == 0:
                parts.append(curr)
                curr = ""
                found = True
                continue
            curr += ch
        if found:
            parts.append(curr)
            if len(parts) >= 2:
                return Implies(parse_formula(parts[0]), parse_formula("→".join(parts[1:])))
        # fallback
        l, r = s.split("→", 1)
        return Implies(parse_formula(l), parse_formula(r))

    # Дизъюнкция (только верхний уровень)
    if "∨" in s:
        parts = []
        depth = 0
        curr = ""
        for ch in s:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "∨" and depth == 0:
                parts.append(curr)
                curr = ""
                continue
            curr += ch
        if parts:
            parts.append(curr)
            return Or([parse_formula(p) for p in parts])

    # Конъюнкция (только верхний уровень)
    if "∧" in s:
        parts = []
        depth = 0
        curr = ""
        for ch in s:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "∧" and depth == 0:
                parts.append(curr)
                curr = ""
                continue
            curr += ch
        if parts:
            parts.append(curr)
            return And([parse_formula(p) for p in parts])

    # Отрицание
    if s.startswith("¬"):
        return Not(parse_formula(s[1:]))

    return parse_atom(s)


# ========== Преобразования логических формул ==========

def eliminate_implications(formula: Node):
    if isinstance(formula, Implies):
        return Or([
            Not(eliminate_implications(formula.left)),
            eliminate_implications(formula.right)
        ])
    elif isinstance(formula, And):
        return And([eliminate_implications(c) for c in formula.children])
    elif isinstance(formula, Or):
        return Or([eliminate_implications(c) for c in formula.children])
    elif isinstance(formula, Not):
        return Not(eliminate_implications(formula.child))
    elif isinstance(formula, (ForAll, Exists)):
        return type(formula)(formula.var, eliminate_implications(formula.body))
    else:
        return formula

def move_nots_inwards(formula: Node):
    if isinstance(formula, Not):
        child = formula.child
        # двойное отрицание
        if isinstance(child, Not):
            return move_nots_inwards(child.child)
        # Де Морган
        if isinstance(child, And):
            return Or([move_nots_inwards(Not(c)) for c in child.children])
        if isinstance(child, Or):
            return And([move_nots_inwards(Not(c)) for c in child.children])
        # Кванторы: инвертируем квантор при отрицании
        if isinstance(child, ForAll):
            # ¬∀x P = ∃x ¬P
            return Exists(child.var, move_nots_inwards(Not(child.body)))
        if isinstance(child, Exists):
            # ¬∃x P = ∀x ¬P
            return ForAll(child.var, move_nots_inwards(Not(child.body)))
        return Not(move_nots_inwards(child))
    elif isinstance(formula, (And, Or)):
        return type(formula)([move_nots_inwards(c) for c in formula.children])
    elif isinstance(formula, (ForAll, Exists)):
        return type(formula)(formula.var, move_nots_inwards(formula.body))
    else:
        return formula


def prenex_normal_form(formula: Node):
    """Кванторы наружу (простая версия)"""
    def pull(formula):
        if isinstance(formula, (And, Or)):
            qs = []
            new_children = []
            for c in formula.children:
                pulled, qs1 = pull(c)
                new_children.append(pulled)
                qs += qs1
            result = type(formula)(new_children)
            return result, qs
        if isinstance(formula, (ForAll, Exists)):
            subf, qs = pull(formula.body)
            # добавляем текущий квантор в список (в конец — порядок восстанавливается позже)
            return subf, qs + [(type(formula), formula.var)]
        return formula, []
    core, qs = pull(formula)
    for Q, var in reversed(qs):
        core = Q(var, core)
    return core

# ========== Сколемизация ==========

skolem_count = itertools.count(1)
def skolemize(formula, env=None):
    """
    Перевод формулы в сколемовскую форму: экзистенциальные кванторы заменяются функциями/константами,
    универсальные — остаются, но переменные фиксируются.
    """
    if env is None:
        env = []
    if isinstance(formula, ForAll):
        return ForAll(formula.var, skolemize(formula.body, env + [formula.var]))
    if isinstance(formula, Exists):
        # Каждая новая переменная — функция от окружения
        num = next(skolem_count)
        name = f"sk{num}"
        if env:
            args = [Var(var) for var in env]
            replacement = Function(name, args)
        else:
            replacement = Const(name)
        return skolemize(substitute(formula.body, formula.var, replacement), env)
    if isinstance(formula, (And, Or)):
        return type(formula)([skolemize(c, env) for c in formula.children])
    if isinstance(formula, Not):
        return Not(skolemize(formula.child, env))
    else:
        return formula

def substitute(formula, var, term):
    # Traverse and replace all Var(var) with term
    if isinstance(formula, Var):
        return term if formula.name == var else formula
    elif isinstance(formula, Const):
        return formula
    elif isinstance(formula, Function):
        return Function(formula.name, [substitute(a, var, term) for a in formula.args])
    elif isinstance(formula, Predicate):
        return Predicate(formula.name, [substitute(a, var, term) for a in formula.args])
    elif isinstance(formula, (And, Or)):
        return type(formula)([substitute(c, var, term) for c in formula.children])
    elif isinstance(formula, Not):
        return Not(substitute(formula.child, var, term))
    elif isinstance(formula, (ForAll, Exists)):
        if formula.var == var:
            return formula
        return type(formula)(formula.var, substitute(formula.body, var, term))
    else:
        return formula

# ========== КНФ ==========

def distribute_or_over_and(f):
    if isinstance(f, (Predicate, Var, Const, Function, Not)):
        return f
    if isinstance(f, And):
        return And([distribute_or_over_and(c) for c in f.children])
    if isinstance(f, Or):
        children = [distribute_or_over_and(c) for c in f.children]
        # ищем конъюнкцию среди детей (правило распределения)
        for i, c in enumerate(children):
            if isinstance(c, And):
                rest = [ch for j, ch in enumerate(children) if j != i]
                new_and_children = []
                for conj_part in c.children:
                    new_or = Or([conj_part] + rest)
                    new_and_children.append(distribute_or_over_and(new_or))
                return And(new_and_children)
        return Or(children)
    return f

def to_cnf(formula):
    if isinstance(formula, ForAll):
        return to_cnf(formula.body)
    f = distribute_or_over_and(formula)
    def extract_literals(expr):
        if isinstance(expr, Or):
            res = []
            for c in expr.children:
                res += extract_literals(c)
            return res
        elif isinstance(expr, And):
            raise Exception("And внутри Or — ошибка КНФ.")
        else:
            # возвращаем строковое представление литерала
            return [str(expr)]
    def flatten_and(expr):
        if isinstance(expr, And):
            result = []
            for c in expr.children:
                result += flatten_and(c)
            return result
        else:
            return [expr]
    clauses = flatten_and(f)
    result = []
    for clause in clauses:
        result.append(extract_literals(clause))
    
    return result
