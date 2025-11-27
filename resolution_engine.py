"""
Резолюционный движок: склеивает все этапы (парсинг → ПНФ → сколемизация → КНФ)
и запускает метод резолюций с унификацией.
"""

from logic_ast import (
    parse_formula,
    eliminate_implications,
    move_nots_inwards,
    prenex_normal_form,
    skolemize,
    to_cnf
)
import re


class LogicResolutionEngine:
    """
    Основной движок для доказательства логических утверждений.
    Вход: список формул (посылки) и цель.
    Выход: доказано/не доказано + лог шагов.
    """

    def solve(self, formulas, goal):
        """
        Главная функция: принимает формулы и цель (строки),
        прогоняет через все преобразования, запускает резолюцию.
        """
        steps = []
        all_clauses_strs = []
        
        # Шаг 1: обрабатываем посылки
        for f in formulas:
            # Полный пайплайн: парсинг → удаление → → ПНФ → сколемизация → КНФ
            node1 = parse_formula(f)
            node2 = eliminate_implications(node1)
            node3 = move_nots_inwards(node2)
            node4 = prenex_normal_form(node3)
            node5 = skolemize(node4)
            cnf_clauses = to_cnf(node5)
            
            # Добавляем клаузы в общую базу
            for c in cnf_clauses:
                all_clauses_strs.append(tuple(c))
                steps.append(f"[КНФ] {c}")

        # Шаг 2: отрицание цели (доказательство от противного)
        neg_goal = goal
        if neg_goal.startswith("¬"):
            neg_goal_str = neg_goal[1:]  # убираем ¬, если уже есть
        else:
            neg_goal_str = "¬" + neg_goal
        
        # Тот же пайплайн для отрицания цели
        node1g = parse_formula(neg_goal_str)
        node2g = eliminate_implications(node1g)
        node3g = move_nots_inwards(node2g)
        node4g = prenex_normal_form(node3g)
        node5g = skolemize(node4g)
        cnf_goal = to_cnf(node5g)
        
        for c in cnf_goal:
            all_clauses_strs.append(tuple(c))
            steps.append(f"[КНФ] (отрицание цели) {c}")

        # Шаг 3: запускаем резолюцию
        result, deriv = self.dumb_resolution(all_clauses_strs)
        steps.extend(deriv)
        
        return {"proven": result, "steps": steps}

    def dumb_resolution(self, clauses):
        """
        Метод резолюций с унификацией.
        Ищем противоположные литералы в разных клаузах, унифицируем их,
        строим резольвенту. Если получаем пустую клаузу — доказано.
        """
        set_clauses = set(tuple(c) for c in clauses)
        log = ["Резолюция с унификацией переменных"]
        clauses_list = list(set_clauses)
        made_new = True
        
        while made_new:
            made_new = False
            new_clauses = []
            
            # Перебираем пары клауз
            for i, a in enumerate(clauses_list):
                for j, b in enumerate(clauses_list):
                    if i >= j:
                        continue  # каждую пару только один раз
                    
                    lits_a = set(a)
                    lits_b = set(b)
                    
                    # Ищем противоположные литералы
                    for lit1 in lits_a:
                        for lit2 in lits_b:
                            # XOR: один с ¬, другой без
                            if (lit1.startswith('¬') ^ lit2.startswith('¬')):
                                subst = self.unify_literals(lit1, lit2)
                                
                                if subst is not None:
                                    log.append(f"Унификация: {lit1} <-> {lit2} под {subst}")

                                    # Строим резольвенту: убираем lit1 и lit2
                                    new_lits = (lits_a - {lit1}) | (lits_b - {lit2})
                                    
                                    # Применяем подстановку ко всем оставшимся литералам
                                    def apply_subst(lit):
                                        m = re.match(r'(¬?)(\w+)\((.*)\)', lit)
                                        if not m:
                                            return lit
                                        pred, args = m.group(2), m.group(3)
                                        new_args = []
                                        for arg in args.split(','):
                                            key = arg.strip()
                                            new_args.append(subst.get(key, key))
                                        return f"{m.group(1)}{pred}({','.join(new_args)})"
                                    
                                    new_lits = set([apply_subst(l) for l in new_lits if l.strip()])
                                    log.append(f"Резолюция: {a} + {b} → {sorted(new_lits) if new_lits else 'ПУСТАЯ КЛАУЗА'}")

                                    # Пустая клауза = противоречие = цель доказана
                                    if not new_lits:
                                        log.append("[ПУСТАЯ КЛАУЗА] Противоречие!")
                                        return True, log

                                    # Добавляем новую клаузу, если её раньше не было
                                    new_clause = tuple(sorted(new_lits))
                                    if new_clause not in set_clauses:
                                        new_clauses.append(new_clause)
                                        set_clauses.add(new_clause)
                                        made_new = True
            
            clauses_list.extend(new_clauses)
        
        log.append("Нет пустой клаузы — не доказано.")
        return False, log

    def unify_literals(self, lit1, lit2):
        """
        Унификация двух литералов: пытаемся подобрать подстановку переменных,
        чтобы они совпали. Переменные — строчные буквы (x, y), константы — всё остальное.
        Возвращает словарь подстановки или None, если унификация невозможна.
        """
        # Убираем отрицания
        core1 = lit1[1:] if lit1.startswith('¬') else lit1
        core2 = lit2[1:] if lit2.startswith('¬') else lit2
        
        # Разбираем предикат и аргументы
        m1 = re.match(r'(\w+)\((.*)\)', core1)
        m2 = re.match(r'(\w+)\((.*)\)', core2)
        
        # Предикаты должны совпадать
        if not m1 or not m2 or m1.group(1) != m2.group(1):
            return None
        
        args1 = [a.strip() for a in m1.group(2).split(',')]
        args2 = [a.strip() for a in m2.group(2).split(',')]
        
        # Количество аргументов должно совпадать
        if len(args1) != len(args2):
            return None
        
        # Строим подстановку
        subst = {}
        for a, b in zip(args1, args2):
            if a == b:
                continue  # одинаковые — ок
            elif a.islower():
                subst[a] = b  # a — переменная, заменяем на b
            elif b.islower():
                subst[b] = a  # b — переменная, заменяем на a
            else:
                # Обе константы и разные — унификация невозможна
                return None
        
        return subst
