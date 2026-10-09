# GenTXT

Aplicativo desktop para gerar arquivos do SPED Fiscal (EFD ICMS/IPI) a partir dos dados da empresa e, opcionalmente, de arquivos XML de NF-e.

## Recursos

- Tela inicial para escolher o tipo de escrituração.
- Gerador SPED Fiscal ICMS/IPI disponível.
- SPED Contribuições, ECF e ECD aparecem no menu como **Em breve**.
- Importação opcional de arquivos XML de NF-e.
- Arquivos gerados em `downloads/arquivos/`.

## Requisitos

- Windows 10 ou mais recente.
- Python para Windows com Tcl/Tk habilitado (incluído na instalação padrão do python.org).
- Não são necessárias bibliotecas Python de terceiros.

## Baixar e executar

1. No GitHub, selecione **Code > Download ZIP** e extraia o arquivo baixado.
2. Se necessário, instale o Python para Windows. Durante a instalação, mantenha o suporte a Tcl/Tk habilitado.
3. Abra `abrir_gerador_sped.bat` na pasta extraída. O inicializador procura `pythonw.exe` nas instalações comuns do Python e abre a interface sem deixar uma janela do CMD aberta.
4. Escolha **SPED Fiscal ICMS/IPI**, preencha os dados e, se quiser, selecione os XMLs das NF-e.
5. O arquivo gerado será salvo em `downloads/arquivos/`.

Também é possível executar pelo terminal com `python gerador_sped_c100.py`.

## Build automático de release

O projeto inclui um workflow do GitHub Actions em `.github/workflows/build-release.yml` que:

- monta o executável para Windows com PyInstaller;
- inclui a logo no ícone do arquivo `.exe` e na janela do aplicativo;
- gera o artefato no GitHub Actions;
- publica `GenTXT.exe` automaticamente em um release quando o código é enviado com uma tag no formato `v*`.

Para disparar a build manualmente, use a ação **Run workflow** no GitHub.

## Observações

- Os demais tipos de SPED ainda não possuem formulários nem geração de arquivos.
- Os arquivos gerados devem ser conferidos no PVA correspondente antes da transmissão.
- Arquivos XML, PDFs, capturas de tela e saídas locais são ignorados pelo Git para evitar publicar dados fiscais ou pessoais acidentalmente.
- Nenhuma licença de uso ou redistribuição foi definida para o código.

[⬇️ Baixar GenTXT para Windows](https://github.com/AlbuquerqueGabriel22/Gerador-de-Speed-Fiscal-ICMS/releases/latest/download/GenTXT.exe)