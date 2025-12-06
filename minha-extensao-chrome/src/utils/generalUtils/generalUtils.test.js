import { print } from "./generalUtils";
import { TIPOS_MENSAGEM } from "../../shared_config/constants";
import { jest } from '@jest/globals';
describe("função print", () => {
  beforeEach(() => {
    jest.clearAllMocks(); // Limpa os mocks entre os testes
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });
  
  it("não deve imprimir nada quando modo_dev está falso", () => {
    TIPOS_MENSAGEM.modo_dev = false;
    const logSpy = jest.spyOn(console, "log");
    print("Testando");
    expect(logSpy).not.toHaveBeenCalled();
  });

  it("deve usar console.log por padrão quando modo_dev está verdadeiro", () => {
    TIPOS_MENSAGEM.modo_dev = true;
    const logSpy = jest.spyOn(console, "log").mockImplementation(() => {});
    print("Mensagem padrão");
    expect(logSpy).toHaveBeenCalledWith("Mensagem padrão");
  });

  it("deve usar console.warn quando último argumento é 'warn'", () => {
    TIPOS_MENSAGEM.modo_dev = true;
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    print("Aviso", "warn");
    expect(warnSpy).toHaveBeenCalledWith("Aviso");
  });

  it("deve usar console.error quando último argumento é 'error'", () => {
    TIPOS_MENSAGEM.modo_dev = true;
    const errorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    print("Erro crítico", "error");
    expect(errorSpy).toHaveBeenCalledWith("Erro crítico");
  });

  it("deve usar alert quando último argumento é 'alert'", () => {
    TIPOS_MENSAGEM.modo_dev = true;
    window.alert = jest.fn(); // Mocka o alert
    print("Mensagem de alerta", "alert");
    expect(window.alert).toHaveBeenCalledWith("Mensagem de alerta");
  });

  it("deve formatar objetos como JSON", () => {
    TIPOS_MENSAGEM.modo_dev = true;
    const logSpy = jest.spyOn(console, "log").mockImplementation(() => {});
    const obj = { nome: "Cain", ativo: true };
    print(obj);
    expect(logSpy).toHaveBeenCalledWith(JSON.stringify(obj, null, 2));
  });
});
