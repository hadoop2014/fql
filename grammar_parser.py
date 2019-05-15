#!/usr/bin/env python
# coding: utf8
#
#
# @file:    grammar_parser
# @author:  chosen0ne(louzhenlin86@126.com)
# @date:    2015/01/19 22:08:25

import re
import time
import os.path
import glob
import os
import accu_func
from datetime import datetime
from collections import OrderedDict
from ply import yacc
from lex_parser import *
from print_utils import FieldPrinter

'''
grammar:
    statement : SELECT select_statement from_statement where_statement
              | SELECT select_statement where_statement
              | SELECT select_statement from_statement
              | SELECT where_statement
              | SELECT select_statement
              | SELECT from_statement

    select_statement : fields_select_stmt
                     | accu_func_stmt

    fields_select_stmt : fields_select_stmt ','  NAME
                       | fields_select_stmt ','  SIZE
                       | fields_select_stmt ','  CTIME
                       | fields_select_stmt ','  MTIME
                       | fields_select_stmt ','  ATIME
                       | NAME
                       | SIZE
                       | CTIME
                       | MTIME
                       | ATIME
                       | '*'

    from_statement : FROM FNAME

    where_statement : WHERE condition_statement

    accu_field : ATIME
               | MTIME
               | CTIME
               | SIZE

    accu_func_stmt : AVG '(' accu_field ')'
                   | MAX '(' accu_field ')'
                   | MIN '(' accu_field ')'
                   | COUNT '(' '*' ')'
                   | accu_func_stmt ',' AVG '(' accu_field ')'
                   | accu_func_stmt ',' MAX '(' accu_field ')'
                   | accu_func_stmt ',' MIN '(' accu_field ')'
                   | accu_func_stmt ',' COUNT '(' '*' ')'
                   | accu_func_stmt ',' SUM '(' SIZE ')'

    condition_statement : condition_statement OR and_condition
                        | and_condition

    and_condition : and_condition AND factor
                  | factor

    factor : name_factor
           | size_factor
           | ctime_factor
           | mtime_factor
           | atime_factor
           | '(' condition_statement ')'
           | NOT factor

    name_factor : NAME '=' QUOTE FNAME QUOTE
                | NAME LIKE QUOTE FNAME QUOTE

    size_factor : SIZE '=' NUMBER
                | SIZE '>' NUMBER
                | SIZE '<' NUMBER
                | SIZE NE NUMBER
                | SIZE GE NUMBER
                | SIZE LE NUMBER

    datetime_factor : DATE
                    | DATE TIME

    ctime_factor : CTIME '=' datetime_factor
                 | CTIME '>' datetime_factor
                 | CTIME GE datetime_factor
                 | CTIME '<' datetime_factor
                 | CTIME LE datetime_factor
                 | CTIME NE datetime_factor

    mtime_factor : MTIME '=' datetime_factor
                 | MTIME '>' datetime_factor
                 | MTIME GE datetime_factor
                 | MTIME '<' datetime_factor
                 | MTIME LE datetime_factor
                 | MTIME NE datetime_factor

    atime_factor : ATIME '=' datetime_factor
                 | ATIME '>' datetime_factor
                 | ATIME GE datetime_factor
                 | ATIME '<' datetime_factor
                 | ATIME LE datetime_factor
                 | ATIME NE datetime_factor

'''

# used to compare file stats, such as st_size, st_ctime, st_atime...
cmp_operators = {
        '=': lambda field, val: lambda finfo: getattr(finfo['stat'], field) == val,
        '>': lambda field, val: lambda finfo: getattr(finfo['stat'], field) > val,
        '<': lambda field, val: lambda finfo: getattr(finfo['stat'], field) < val,
        '!=': lambda field, val: lambda finfo: getattr(finfo['stat'], field) != val,
        '>=': lambda field, val: lambda finfo: getattr(finfo['stat'], field) >= val,
        '<=': lambda field, val: lambda finfo: getattr(finfo['stat'], field) <= val
}


def execute(s_stmt, f_stmt, w_stmt):
    if not s_stmt:
        s_stmt = ['*']
    if not f_stmt:
        f_stmt = '.'
    if not w_stmt:
        w_stmt = lambda finfo: True

    show_fields = OrderedDict()
    accu_funcs = OrderedDict()
    for s in s_stmt:
        if isinstance(s, accu_func.AccuFuncCls):
            accu_funcs['_'.join(s.desp())] = s
        else:
            show_fields[s] = 1

    accu_funcs = accu_funcs.values()
    if '*' in show_fields:
        show_fields = ['*']
    else:
        show_fields = show_fields.keys()

    # print table, info for echo row
    printer = FieldPrinter(f_stmt, show_fields, accu_funcs)
    printer.print_title()

    travel_file_tree(f_stmt, accu_funcs, w_stmt, printer)

    # print accumulative func
    printer.print_accu_funcs()


def travel_file_tree(start_point, accu_funcs, selector, printer):
    g = glob.glob(start_point + '/*')
    for f in g:
        statinfo = os.stat(f)
        fname = os.path.basename(f)
        finfo = {'name': fname, 'stat': statinfo}
        if selector(finfo):
            printer.print_finfo(fname, statinfo)

            for accufunc in accu_funcs:
                accufunc(finfo, fname)

        if os.path.isdir(f):
            travel_file_tree(f, accu_funcs, selector, printer)


def p_statement(p):
    '''
        statement : SELECT select_statement from_statement where_statement
                  | SELECT select_statement where_statement
                  | SELECT select_statement from_statement
                  | SELECT where_statement
                  | SELECT select_statement
                  | SELECT from_statement
    '''
    s_stmt, f_stmt, w_stmt = None, None, None
    if len(p) == 5:
        s_stmt = p[2][1]
        f_stmt = p[3][1]
        w_stmt = p[4][1]
    elif len(p) == 4:
        stmt_type, func = p[3]
        if stmt_type == 'from':
            s_stmt, f_stmt = p[2][1], func
        elif stmt_type == 'where':
            s_stmt, w_stmt = p[2][1], func
    elif len(p) == 3:
        stmt_type, func = p[2]
        if stmt_type == 'from':
            f_stmt = func
        elif stmt_type == 'where':
            w_stmt = func
        elif stmt_type == 'select':
            s_stmt = func

    execute(s_stmt, f_stmt, w_stmt)


def p_select_stmt(p):
    '''
        select_statement : fields_select_stmt
                         | accu_func_stmt
    '''
    p[0] = ('select', p[1])


def p_fields_select_stmt(p):
    '''
        fields_select_stmt : fields_select_stmt ','  NAME
                           | fields_select_stmt ','  SIZE
                           | fields_select_stmt ','  CTIME
                           | fields_select_stmt ','  MTIME
                           | fields_select_stmt ','  ATIME
                           | NAME
                           | SIZE
                           | CTIME
                           | MTIME
                           | ATIME
                           | '*'
    '''
    if not p[0]:
        p[0] = []

    if len(p) == 4:
        p[0].extend(p[1])
        p[0].append(p[3])
    elif len(p) == 2:
        p[0].append(p[1])


def p_accu_field(p):
    '''
        accu_field : ATIME
                   | MTIME
                   | CTIME
                   | SIZE
    '''
    p[0] = p[1]


def p_accu_func_stmt1(p):
    '''
        accu_func_stmt : AVG '(' accu_field ')'
                       | MAX '(' accu_field ')'
                       | MIN '(' accu_field ')'
                       | COUNT '(' '*' ')'
                       | SUM '(' SIZE ')'
    '''
    f = 'st_' + p[3].lower()
    op = p[1]
    accu_obj_name = op[0].upper() + op[1:].lower() + 'FuncCls'
    accu_obj = accu_func.__dict__[accu_obj_name]
    p[0] = [accu_obj(f)]


def p_accu_func_stmt2(p):
    '''
        accu_func_stmt : accu_func_stmt ',' AVG '(' accu_field ')'
                       | accu_func_stmt ',' MAX '(' accu_field ')'
                       | accu_func_stmt ',' MIN '(' accu_field ')'
                       | accu_func_stmt ',' COUNT '(' '*' ')'
                       | accu_func_stmt ',' SUM '(' SIZE ')'
    '''
    if not p[0]:
        p[0] = []

    f = 'st_' + p[5].lower()
    op = p[3]
    accu_obj_name = op[0].upper() + op[1:].lower() + 'FuncCls'
    accu_obj = accu_func.__dict__[accu_obj_name]

    p[0].extend(p[1])
    p[0].append(accu_obj(f))


def p_from_stmt(p):
    'from_statement : FROM FNAME'
    p[0] = ('from', p[2])


def p_where_stmt(p):
    'where_statement : WHERE condition_statement'
    p[0] = ('where', p[2])


def p_condition_stmt1(p):
    'condition_statement : condition_statement OR and_condition'
    p1, p2 = p[1], p[3]
    p[0] = lambda finfo: p1(finfo) or p2(finfo)


def p_condition_stmt2(p):
    'condition_statement : and_condition'
    p[0] = p[1]


def p_and_condition1(p):
    'and_condition : and_condition AND factor'
    p1, p2 = p[1], p[3]
    p[0] = lambda finfo: p1(finfo) and p2(finfo)


def p_and_condition2(p):
    'and_condition : factor'
    p[0] = p[1]


def p_factor(p):
    '''
        factor : name_factor
               | size_factor
               | ctime_factor
               | mtime_factor
               | atime_factor
               | '(' condition_statement ')'
               | NOT factor
    '''
    if len(p) == 2:
        p[0] = p[1]
    elif len(p) == 3:
        p1 = p[2]
        p[0] = lambda finfo: not p1(finfo)
    elif len(p) == 4:
        p[0] = p[2]


def p_name_factor(p):
    '''
        name_factor : NAME '=' QUOTE FNAME QUOTE
                    | NAME LIKE QUOTE FNAME QUOTE
    '''
    _, _, op, _, fname, _ = p
    if op == '=':
        p[0] = lambda finfo: finfo['name'] == fname
    else:
        fname = fname.replace('.', '\.')
        fname = fname.replace('%', '.*')
        pattern = re.compile(fname)
        p[0] = lambda finfo: pattern.match(finfo['name']) is not None


def p_size_factor(p):
    '''
        size_factor : SIZE '=' NUMBER
                    | SIZE '>' NUMBER
                    | SIZE '<' NUMBER
                    | SIZE NE NUMBER
                    | SIZE GE NUMBER
                    | SIZE LE NUMBER
    '''
    _, _, op, fsize = p
    cmp_func = cmp_operators[op]
    p[0] = cmp_func('st_size', fsize)


def p_datetime_factor(p):
    '''
        datetime_factor : DATE
                        | DATE TIME
    '''
    if len(p) == 2:
        p[0] = datetime.strptime(p[1], '%Y-%m-%d')
    else:
        p[0] = datetime.strptime(p[1] + ' ' + p[2], '%Y-%m-%d %H:%M:%S')

def p_ctime_factor(p):
    '''
        ctime_factor : CTIME '=' datetime_factor
                     | CTIME '>' datetime_factor
                     | CTIME GE datetime_factor
                     | CTIME '<' datetime_factor
                     | CTIME LE datetime_factor
                     | CTIME NE datetime_factor
    '''
    time_proc(p)


def p_mtime_factor(p):
    '''
        mtime_factor : MTIME '=' datetime_factor
                     | MTIME '>' datetime_factor
                     | MTIME GE datetime_factor
                     | MTIME '<' datetime_factor
                     | MTIME LE datetime_factor
                     | MTIME NE datetime_factor
    '''
    time_proc(p)


def p_atime_factor(p):
    '''
        atime_factor : ATIME '=' datetime_factor
                     | ATIME '>' datetime_factor
                     | ATIME GE datetime_factor
                     | ATIME '<' datetime_factor
                     | ATIME LE datetime_factor
                     | ATIME NE datetime_factor
    '''
    time_proc(p)


def time_proc(p):
    _, field_name, op, d = p
    d = time.mktime(d.timetuple())
    field_name = 'st_' + field_name.lower()

    cmp_func = cmp_operators[op]
    p[0] = cmp_func(field_name, d)


def p_error(p):
    if not p:
        print 'End of file'
        return
    print 'parse error, unexpected token:', p.type


yacc.yacc()


if __name__ == '__main__':
    yacc.yacc()
    stmt = 'select $name, avg($size) from . where $size > 1'
    yacc.parse(stmt)
