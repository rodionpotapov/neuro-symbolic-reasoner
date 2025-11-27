"""
Модуль для работы с логическими формулами.
Включает AST (абстрактное синтаксическое дерево), парсер и все преобразования
для метода резолюций: удаление импликаций, ПНФ, сколемизация, КНФ.
"""

import re
import itertools
from typing import List, Set, Dict, Union, Optional


# ========== AST-узлы: представление формулы в памяти ==========

class Node:
    """Базовый класс для всех узлов формулы."""
    pass


class Var(Node):
    """Переменная логики предикатов (x, y, z)."""
    def __init__(self, name: str):
        self.name = name
    def __repr__(self):
        return self.name


class Const(Node):
    """Константа — конкретный объект (Сократ, Вася)."""
    def __init__(self, name: str):
        self.name = name
    def __repr__(self):
        return self.name


class Function(Node):
    """
    Функциональный терм, например father(x) или sk1(x,y).
    Используется в основном для сколемовских функций.
    """
    def __init__(self, name: str, args: List[Node]):
        self.name = name
        self.args = args
    
    def __repr__(self):
        if self.args:
            return f"{self.name}({','.join(map(str, self.args))})"
        return self.name


class Predicate(Node):
    """Предикат: Человек(x), Смертен(Сократ)."""
    def __init__(self, name: str, args: List[Node]):
        self.name = name
        self.args = args
    
    def __repr__(self):
        return f"{self.name}({','.join(map(str, self.args))})"


class Not(Node):
    """Отрицание: ¬A."""
    def __init__(self, child: Node):
        self.child = child
    
    def __repr__(self):
        return f"¬{self.child}"


class And(Node):
    """Конъюнкция: A ∧ B ∧ C."""
    def __init__(self, children: List[Node]):
        self.children = children
    
    def __repr__(self):
        return "(" + " ∧ ".join(map(str, self.children)) + ")"


class Or(Node):
    """Дизъюнкция: A ∨ B ∨ C."""
    def __init__(self, children: List[Node]):
        self.children = children
    
    def __repr__(self):
        return "(" + " ∨ ".join(map(str, self.children)) + ")"


class Implies(Node):
    """Импликация: A → B."""
    def __init__(self, left: Node, right: Node):
        self.left = left
        self.right = right
    
    def __repr__(self):
        return f"({self.left} → {self.right})"


class ForAll(Node):
    """Универсальный квантор: ∀x body."""
    def __init__(self, var: str, body: Node):
        self.var = var
        self.body = body
    
    def __repr__(self):
        return f"(∀{self.var} {self.body})"


class Exists(Node):
    """Квантор существования: ∃x body."""
    def __init__(self, var: str, body: Node):
        self.var = var
        self.body = body
    
    def __repr__(self):
        return f"(∃{self.var} {self.body})"


# ========== Парсер: строка → AST ==========

def parse_formula(s: str) -> Node:
    """
    Парсит строку формулы в AST.
    Вход: "∀x (Человек(x) → Смертен(x))"
    Выход: дерево из узлов ForAll, Implies, Predicate и т.п.
    """
    s = s.replace(" ", "")  # убираем пробелы для удобства

    def parse_atom(atom):
        """Парсит атомарный предикат вида Имя(арг1, арг2, ...)."""
        atom = atom.strip()
        
        # Стандарт: Имя(...)
        m = re.match(r'^([A-Za-zА-Яа-яёЁ0-9_]+)\((.*)\)$', atom)
        if m:
            name = m.group(1)
            rest = m.group(2)
            args = []
            
            if rest.strip() == "":
                return Predicate(name, [])
            
            # Разбиваем аргументы с учётом вложенных скобок
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
            
            # Каждый аргумент: заглавная буква → Const, иначе → Var
            for part in parts:
                part = part.strip()
                part = re.sub(r'[^A-Za-zА-Яа-яёЁ0-9_]', '', part)
                if not part:
                    continue
                if part[0].isupper():
                    args.append(Const(part))
                else:
                    args.append(Var(part))
            
            return Predicate(name, args)
        
        # Если нет скобок — считаем это предикат без аргументов
        atom_no_parens = re.sub(r'[\(\)]', '', atom)
        atom_no_parens = re.sub(r'[^A-Za-zА-Яа-яёЁ0-9_]', '', atom_no_parens)
        return Predicate(atom_no_parens, [])

    # Снятие внешних скобок
    if s.startswith("(") and s.endswith(")"):
        depth = 0
        balanced = True
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth == 0 and i < len(s) - 1:
                balanced = False
                break
        if balanced:
            s = s[1:-1]

    # Кванторы
    m = re.match(r'∀([A-Za-z0-9_]+)\((.+)\)$', s)
    if m:
        return ForAll(m.group(1), parse_formula(m.group(2)))
    m = re.match(r'∃([A-Za-z0-9_]+)\((.+)\)$', s)
    if m:
        return Exists(m.group(1), parse_formula(m.group(2)))

    # Импликация
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
        l, r = s.split("→", 1)
        return Implies(parse_formula(l), parse_formula(r))

    # Дизъюнкция
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

    # Конъюнкция
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


# ========== Преобразования формул ==========

def eliminate_implications(formula: Node):
    """
    Удаление импликаций: A → B превращается в ¬A ∨ B.
    Стандартный первый шаг перед КНФ.
    """
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
    """
    Проталкивание отрицаний внутрь (законы Де Моргана).
    Цель: ¬ должны стоять только перед предикатами.
    """
    if isinstance(formula, Not):
        child = formula.child
        
        # Двойное отрицание: ¬¬A = A
        if isinstance(child, Not):
            return move_nots_inwards(child.child)
        
        # Де Морган: ¬(A ∧ B) = ¬A ∨ ¬B
        if isinstance(child, And):
            return Or([move_nots_inwards(Not(c)) for c in child.children])
        
        # Де Морган: ¬(A ∨ B) = ¬A ∧ ¬B
        if isinstance(child, Or):
            return And([move_nots_inwards(Not(c)) for c in child.children])
        
        # Отрицание кванторов: ¬∀x P = ∃x ¬P, ¬∃x P = ∀x ¬P
        if isinstance(child, ForAll):
            return Exists(child.var, move_nots_inwards(Not(child.body)))
        if isinstance(child, Exists):
            return ForAll(child.var, move_nots_inwards(Not(child.body)))
        
        return Not(move_nots_inwards(child))
    
    elif isinstance(formula, (And, Or)):
        return type(formula)([move_nots_inwards(c) for c in formula.children])
    elif isinstance(formula, (ForAll, Exists)):
        return type(formula)(formula.var, move_nots_inwards(formula.body))
    else:
        return formula


def prenex_normal_form(formula: Node):
    """
    Пренексная нормальная форма: все кванторы выносятся в префикс.
    Например: ∀x (P(x) ∧ ∃y Q(x,y)) → ∀x ∃y (P(x) ∧ Q(x,y))
    """
    def pull(formula):
        """Рекурсивно вытягивает кванторы наружу."""
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
            return subf, qs + [(type(formula), formula.var)]
        
        return formula, []
    
    core, qs = pull(formula)
    # Оборачиваем ядро кванторами в обратном порядке
    for Q, var in reversed(qs):
        core = Q(var, core)
    return core


# ========== Сколемизация ==========

skolem_count = itertools.count(1)  # генератор имён sk1, sk2, ...

def skolemize(formula, env=None):
    """
    Сколемизация: убираем ∃, заменяя их на новые функции/константы.
    Пример: ∀x ∃y P(x,y) → ∀x P(x, sk1(x))
    """
    if env is None:
        env = []
    
    # Универсальный квантор: добавляем переменную в окружение
    if isinstance(formula, ForAll):
        return ForAll(formula.var, skolemize(formula.body, env + [formula.var]))
    
    # Экзистенциальный квантор: заменяем на сколемовскую функцию/константу
    if isinstance(formula, Exists):
        num = next(skolem_count)
        name = f"sk{num}"
        
        if env:
            # Если есть внешние ∀ → функция от них
            args = [Var(var) for var in env]
            replacement = Function(name, args)
        else:
            # Иначе → константа
            replacement = Const(name)
        
        # Подставляем во всю формулу и продолжаем сколемизацию
        return skolemize(substitute(formula.body, formula.var, replacement), env)
    
    if isinstance(formula, (And, Or)):
        return type(formula)([skolemize(c, env) for c in formula.children])
    if isinstance(formula, Not):
        return Not(skolemize(formula.child, env))
    else:
        return formula


def substitute(formula, var, term):
    """Заменяет все вхождения переменной var на терм term."""
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
            return formula  # не заходим внутрь — новая область видимости
        return type(formula)(formula.var, substitute(formula.body, var, term))
    else:
        return formula


# ========== КНФ ==========

def distribute_or_over_and(f):
    """
    Распределение ∨ над ∧: (A ∧ B) ∨ C = (A ∨ C) ∧ (B ∨ C).
    Нужно для получения КНФ.
    """
    if isinstance(f, (Predicate, Var, Const, Function, Not)):
        return f
    
    if isinstance(f, And):
        return And([distribute_or_over_and(c) for c in f.children])
    
    if isinstance(f, Or):
        children = [distribute_or_over_and(c) for c in f.children]
        
        # Ищем конъюнкцию среди детей
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
    """
    Преобразование в КНФ (конъюнктивная нормальная форма).
    Возвращает список клауз, где каждая клауза — список литералов-строк.
    """
    # Универсальные кванторы на этом этапе можно убрать
    if isinstance(formula, ForAll):
        return to_cnf(formula.body)
    
    # Распределяем ∨ над ∧
    f = distribute_or_over_and(formula)
    
    def extract_literals(expr):
        """Извлекает литералы из дизъюнкции."""
        if isinstance(expr, Or):
            res = []
            for c in expr.children:
                res += extract_literals(c)
            return res
        elif isinstance(expr, And):
            raise Exception("And внутри Or — ошибка КНФ")
        else:
            return [str(expr)]
    
    def flatten_and(expr):
        """Разворачивает вложенные And в плоский список."""
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
