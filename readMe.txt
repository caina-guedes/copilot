https://chatgpt.com/c/681a2251-8d94-800e-b546-312080230107

comando para iniciar o watcher:

PYTHONPATH=. python3 PythonSistemAutomation/main.py

comando para iniciar o server 

PYTHONPATH=. python3 PythonServer/server.py


estou fazendo adaptações pra poder transformar o watcher e o server em 
um processo único, pra isso preciso melhorar a start_runtime do lifecyclaMaster
pois ela foi pensada pra rodar apenas a raiz do processo, agora eu talvez 
vou rodar ela 2 x , uma pro server e outra pro watcher dentro do próprio arquivo do server,
pelo menos essa é minha idéia inicial, mas ai preciso extrair o nome da corotina injetada 
na função pra personalizar a min task com o nome correto, elas ja vão ser protegidas usando
apenas o run_async mas eu estou querendo ser cauteloso.


