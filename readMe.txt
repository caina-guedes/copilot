https://chatgpt.com/c/681a2251-8d94-800e-b546-312080230107

comando para iniciar o watcher:

PYTHONPATH=. python3 PythonSistemAutomation/main.py

comando para iniciar o server 

PYTHONPATH=. python3 PythonServer/server.py


acho que a função de despressionar teclas é a raiz do problema, por ter partes async misturadas,

alem disso a função logo depois da task acabar tbm não deve ter nada async ou demorado, 

e quero verificar se a função default_receiving_function  é async e precisa ser async, pois se

não for necessário posso simplificar bastante as coisas!




