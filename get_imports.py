import os
import re
import pkg_resources

def get_all_imports(start_path):
    all_imports = set()
    # Pastas que não queremos vasculhar (ganho de performance e limpeza)
    ignore_dirs = {'.git', 'venv', 'env', '__pycache__', 'build', 'dist'}

    for root, dirs, files in os.walk(start_path):
        # Remove pastas ignoradas da busca recursiva
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        print("the var dirs is: ",dirs)
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        for line in f:
                            # Regex para capturar 'import modulo' ou 'from modulo import ...'
                            match = re.match(r"^\s*(?:from|import)\s+([\w\d_]+)", line)
                            if match:
                                all_imports.add(match.group(1).lower())
                except Exception as e:
                    print(f"Erro ao ler {file_path}: {e}")
    return all_imports

# 1. Pega a lista de tudo que está REALMENTE instalado no seu ambiente atual
installed_packages = {pkg.key: pkg.version for pkg in pkg_resources.working_set}

# 2. Varre o projeto recursivamente atrás de imports
print("Vasculhando arquivos .py recursivamente...")
project_imports = get_all_imports(".")

# 3. Cruza os dados e gera o arquivo
print("\n--- Dependências Detectadas e Instaladas ---")
found_any = False
with open("requirements_preciso.txt", "w") as f:
    # Ordenar para ficar organizado
    for imp in sorted(project_imports):
        if imp in installed_packages:
            line = f"{imp}=={installed_packages[imp]}"
            print(f"[OK] {line}")
            f.write(line + "\n")
            found_any = True

if not found_any:
    print("Aviso: Nenhum import do seu código bateu com os pacotes instalados via pip.")
else:
    print(f"\nSucesso! O arquivo 'requirements_preciso.txt' foi gerado.")