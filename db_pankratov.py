import pandas as pd
import sqlite3

path = "C:/Users\Ilya\Downloads\Тестовая БД - все таблицы.xlsx"
sl = pd.read_excel(path, sheet_name='СЛ')
ot = pd.read_excel(path, sheet_name='ОТ')
o_m = pd.read_excel(path, sheet_name='О_М')
pr = pd.read_excel(path, sheet_name='ПР')
izhd = pd.read_excel(path, sheet_name='ИЖД')
r_n = pd.read_excel(path, sheet_name='Р_Н')

# Создание in-memory SQLite базы данных
conn = sqlite3.connect(':memory:')

# Загрузка данных в SQLite
sl.to_sql('СЛ', conn, index=False)
ot.to_sql('ОТ', conn, index=False)
o_m.to_sql('О_М', conn, index=False)
pr.to_sql('ПР', conn, index=False)
izhd.to_sql('ИЖД', conn, index=False)
r_n.to_sql('Р_Н', conn, index=False)


def execute_sql_query(query):
    return pd.read_sql_query(query, conn)


# Пример выполнения задания 1.2 через SQL
print("\nЗадание 1.2 - Служащие без иждивенцев:")
query_1_2 = """
SELECT Фамилия, Имя
FROM СЛ
WHERE Код NOT IN (
    SELECT Код
    FROM ИЖД
);
"""
result_1_2 = execute_sql_query(query_1_2)
print(result_1_2)

print("\nЗадание 1.3 - Служащие, не работающие над 'Межеванием':")
query_1_3 = """
SELECT DISTINCT СЛ.Фамилия, СЛ.Имя
FROM СЛ
WHERE СЛ.Код NOT IN (
    SELECT Р_Н.Код
    FROM Р_Н
    JOIN ПР ON Р_Н.Nп = ПР.Nп
    WHERE ПР.Назв = 'Межевание'
);
"""

result_1_3 = execute_sql_query(query_1_3)
print(result_1_3)



print("Задание 1.5 - Кураторы, работающие над проектами вместе с курируемыми:")
query_1_5 = """
SELECT DISTINCT 
    куратор.Фамилия || ' ' || куратор.Имя AS Куратор,
    курируемый.Фамилия || ' ' || курируемый.Имя AS Курируемый,
    ПР.Назв AS Проект
FROM СЛ AS куратор
JOIN СЛ AS курируемый ON куратор.Код = курируемый.КодК
JOIN Р_Н AS рн_куратор ON куратор.Код = рн_куратор.Код
JOIN Р_Н AS рн_курируемый ON курируемый.Код = рн_курируемый.Код
JOIN ПР ON рн_куратор.Nп = ПР.Nп AND рн_курируемый.Nп = ПР.Nп
ORDER BY куратор.Фамилия, курируемый.Фамилия;
"""

result_1_5 = execute_sql_query(query_1_5)
print(result_1_5)
