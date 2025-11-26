from logic_ast import parse_formula, eliminate_implications, move_nots_inwards, prenex_normal_form, skolemize, to_cnf
import re

class LogicResolutionEngine:
    """
    Склеивает все этапы: парсинг -> ПНФ -> Сколемизация -> КНФ -> резолюционный вывод.
    Возвращает: {proven: bool, steps: [string, ...]}
    """

    def solve(self, formulas, goal):
        steps = []
        all_clauses_strs = []
        # 1. Основные формулы
        for f in formulas:
            node1 = parse_formula(f)
            node2 = eliminate_implications(node1)
            node3 = move_nots_inwards(node2)
            node4 = prenex_normal_form(node3)
            node5 = skolemize(node4)
            cnf_clauses = to_cnf(node5)
            for c in cnf_clauses:
                all_clauses_strs.append(tuple(c))
                steps.append(f"[КНФ] {c}")

        # 2. Отрицание цели — корректно!
        # Не ¬(X), а просто ¬X
        neg_goal = goal
        if neg_goal.startswith("¬"):
            neg_goal_str = neg_goal[1:]
        else:
            neg_goal_str = "¬" + neg_goal
        node1g = parse_formula(neg_goal_str)
        node2g = eliminate_implications(node1g)
        node3g = move_nots_inwards(node2g)
        node4g = prenex_normal_form(node3g)
        node5g = skolemize(node4g)
        cnf_goal = to_cnf(node5g)
        for c in cnf_goal:
            all_clauses_strs.append(tuple(c))
            steps.append(f"[КНФ] (отрицание цели) {c}")

        # 3. Резолюция
        result, deriv = self.dumb_resolution(all_clauses_strs)
        steps.extend(deriv)
        return {"proven": result, "steps": steps}

    def dumb_resolution(self, clauses):
        # Резолюция с унификацией переменных!
        set_clauses = set(tuple(c) for c in clauses)
        log = ["Резолюция с унификацией переменных"]
        clauses_list = list(set_clauses)
        made_new = True
        while made_new:
            made_new = False
            new_clauses = []
            for i, a in enumerate(clauses_list):
                for j, b in enumerate(clauses_list):
                    if i >= j:
                        continue
                    lits_a = set(a)
                    lits_b = set(b)
                    for lit1 in lits_a:
                        for lit2 in lits_b:
                            # Противоположные знаки и унифицируемы
                            if (lit1.startswith('¬') ^ lit2.startswith('¬')):
                                subst = self.unify_literals(lit1, lit2)
                                if subst is not None:
                                    log.append(f"Унификация: {lit1} <-> {lit2} под {subst}")

                                    # Новая клауза — без этих литералов, с подстановкой
                                    new_lits = (lits_a - {lit1}) | (lits_b - {lit2})
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

                                    if not new_lits:
                                        log.append("[ПУСТАЯ КЛАУЗА] Противоречие!")
                                        return True, log

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
        Унификация литералов вида "¬П(x)" и "П(Иван)".
        """
        # Убираем отрицания
        core1 = lit1[1:] if lit1.startswith('¬') else lit1
        core2 = lit2[1:] if lit2.startswith('¬') else lit2
        m1 = re.match(r'(\w+)\((.*)\)', core1)
        m2 = re.match(r'(\w+)\((.*)\)', core2)
        if not m1 or not m2 or m1.group(1) != m2.group(1):
            return None
        args1 = [a.strip() for a in m1.group(2).split(',')]
        args2 = [a.strip() for a in m2.group(2).split(',')]
        if len(args1) != len(args2):
            return None
        subst = {}
        for a, b in zip(args1, args2):
            if a == b:
                continue
            elif a.islower():
                subst[a] = b
            elif b.islower():
                subst[b] = a
            else:
                # разные константы — унификация невозможна
                return None
        return subst
