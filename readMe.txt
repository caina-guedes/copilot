https://chatgpt.com/c/681a2251-8d94-800e-b546-312080230107

comando para iniciar o watcher:

PYTHONPATH=. python3 PythonSistemAutomation/main.py

comando para iniciar o server 

PYTHONPATH=. python3 PythonServer/server.py



por sorte consegui pegar um bug que só ocorre quando não tem nenhuma macro gravada.
da erro quando o banco de dados está vazio  ai eu comecei a fazer as correções 
mas isso tem que ser verificado ainda, o proximo passo é rodar o botão de executar 
macro pra ver se vai ocorrer algum erro





estou fazendo adaptações pra poder transformar o watcher e o server em 
um processo único, pra isso preciso melhorar a start_runtime do lifecyclaMaster
pois ela foi pensada pra rodar apenas a raiz do processo, agora eu talvez 
vou rodar ela 2 x , uma pro server e outra pro watcher dentro do próprio arquivo do server,
pelo menos essa é minha idéia inicial, mas ai preciso extrair o nome da corotina injetada 
na função pra personalizar a min task com o nome correto, elas ja vão ser protegidas usando
apenas o run_async mas eu estou querendo ser cauteloso.


meu ultimo comando antes de reiniciar
dism /online /cleanup-image /revertpendingactions

