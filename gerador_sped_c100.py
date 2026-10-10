import os
import re
import sys
import tkinter as tk
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

BASE_DIR = (
    os.path.dirname(sys.executable)
    if getattr(sys, 'frozen', False)
    else os.path.dirname(os.path.abspath(__file__))
)


def resolve_asset_path(nome_arquivo):
    if getattr(sys, 'frozen', False):
        candidatos = [
            os.path.join(os.path.dirname(sys.executable), 'assets', nome_arquivo),
            os.path.join(getattr(sys, '_MEIPASS', ''), 'assets', nome_arquivo),
            os.path.join(getattr(sys, '_MEIPASS', ''), nome_arquivo),
        ]
        for candidato in candidatos:
            if os.path.exists(candidato):
                return candidato

    caminho_local = os.path.join(BASE_DIR, 'assets', nome_arquivo)
    if os.path.exists(caminho_local):
        return caminho_local

    return os.path.join(BASE_DIR, nome_arquivo)


PASTA_SAIDA = os.path.join(BASE_DIR, 'downloads', 'arquivos')

def somente_digitos(valor):
    return re.sub(r'\D', '', valor or '')

def data_efd(valor, nome):
    for formato in ('%d/%m/%Y', '%d%m%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(valor.strip(), formato).strftime('%d%m%Y')
        except ValueError:
            continue
    raise ValueError(f'{nome} inválida. Use DD/MM/AAAA.')

def registro(*valores):
    return '|' + '|'.join(str(valor or '').strip().replace('|', '/') for valor in valores) + '|'

def texto(elemento, tag, ns, padrao=''):
    no = elemento.find(f'ns:{tag}', ns) if elemento is not None else None
    return no.text.strip() if no is not None and no.text else padrao

def valor_sped(valor, padrao='0,00'):
    if not valor:
        return padrao
    try:
        numero = float(valor.replace('.', '').replace(',', '.')) if ',' in valor else float(valor)
        return f'{numero:.2f}'.replace('.', ',')
    except ValueError:
        return padrao

def quantidade_sped(valor):
    """Garante a formatação da quantidade com 5 casas decimais, padrão EFD"""
    if not valor:
        return '0,00000'
    try:
        numero = float(valor.replace('.', '').replace(',', '.')) if ',' in valor else float(valor)
        return f'{numero:.5f}'.replace('.', ',')
    except ValueError:
        return '0,00000'

def cst_icms_sped(valor):
    digitos = somente_digitos(str(valor))
    return digitos.zfill(3) if digitos else '000'

def tributacao_c170(item):
    """Aplica a padronização fiscal solicitada para os itens C170."""
    cst = cst_icms_sped(item.get('cst'))
    cfop = str(item.get('cfop', '')).strip()
    if cst in ('010', '060') and cfop in ('5403', '5405'):
        return {
            'cst': '060',
            'cfop': '5405',
            'bc_icms': '0,00',
            'aliquota': '0,00',
            'icms': '0,00',
        }
    if cst in ('000', '020', '090'):
        return {
            'cst': cst,
            'cfop': cfop,
            'bc_icms': '0,00',
            'aliquota': '0,00',
            'icms': '0,00',
        }
    return {
        'cst': cst,
        'cfop': cfop,
        'bc_icms': valor_sped(item.get('bc_icms')),
        'aliquota': valor_sped(item.get('aliquota')),
        'icms': valor_sped(item.get('icms')),
    }

def data_xml(valor):
    return data_efd(valor.split('T')[0], 'Data da NF-e') if valor else ''

def ler_nfe(caminho):
    ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
    raiz = ET.parse(caminho).getroot()
    inf = raiz.find('.//ns:infNFe', ns)
    if inf is None:
        raise ValueError('XML não contém a tag infNFe')
    
    ide = inf.find('ns:ide', ns)
    emit = inf.find('ns:emit', ns)
    dest = inf.find('ns:dest', ns)
    total = inf.find('.//ns:ICMSTot', ns)
    
    tp_nf = texto(ide, 'tpNF', ns, '1')
    participante = dest if tp_nf == '1' else emit
    cnpj = texto(participante, 'CNPJ', ns) or texto(participante, 'CPF', ns)
    data = data_xml(texto(ide, 'dhEmi', ns) or texto(ide, 'dEmi', ns))
    
    itens = []
    for numero, det in enumerate(inf.findall('ns:det', ns), start=1):
        prod = det.find('ns:prod', ns)
        imposto = det.find('ns:imposto', ns)
        icms = imposto.find('.//ns:ICMS', ns) if imposto is not None else None
        icms_valor = next(iter(icms), None) if icms is not None and len(icms) else None
        
        # Fallback para CSOSN caso seja Simples Nacional
        cst_xml = texto(icms_valor, 'CST', ns) or texto(icms_valor, 'CSOSN', ns) or '00'
        
        itens.append({
            'numero': numero, 'codigo': texto(prod, 'cProd', ns),
            'descricao': texto(prod, 'xProd', ns), 'unidade': texto(prod, 'uCom', ns, 'UN'),
            'quantidade': texto(prod, 'qCom', ns), 'valor': texto(prod, 'vProd', ns),
            'desconto': texto(prod, 'vDesc', ns), 'ncm': texto(prod, 'NCM', ns),
            'cfop': texto(prod, 'CFOP', ns, '5102'), 'cst': cst_xml,
            'bc_icms': texto(icms_valor, 'vBC', ns), 'icms': texto(icms_valor, 'vICMS', ns),
            'aliquota': texto(icms_valor, 'pICMS', ns),
        })
        
    return {
        'ind_oper': tp_nf, 'ind_emit': '0' if tp_nf == '1' else '1',
        'cod_part': cnpj, 'nome_part': texto(participante, 'xNome', ns),
        'mod': texto(ide, 'mod', ns, '55'), 'serie': texto(ide, 'serie', ns, '1'),
        'numero': texto(ide, 'nNF', ns), 'chave': inf.attrib.get('Id', '').replace('NFe', ''),
        'data': data, 'valor': texto(total, 'vNF', ns), 'desconto': texto(total, 'vDesc', ns),
        'mercadoria': texto(total, 'vProd', ns), 'frete': texto(total, 'vFrete', ns),
        'seguro': texto(total, 'vSeg', ns), 'outros': texto(total, 'vOutro', ns),
        'bc_icms': texto(total, 'vBC', ns), 'icms': texto(total, 'vICMS', ns),
        'itens': itens,
    }

def ler_xmls(caminhos):
    notas = []
    for caminho in caminhos or []:
        try:
            notas.append(ler_nfe(caminho))
        except (ET.ParseError, OSError, ValueError) as erro_xml:
            raise ValueError(f'{os.path.basename(caminho)}: {erro_xml}') from erro_xml
    return notas

def gerar_registros_notas(notas):
    participantes = {}
    produtos = {}
    movimento = []
    
    for nota in notas:
        if nota['cod_part']:
            participantes[nota['cod_part']] = nota['nome_part']
        for item in nota['itens']:
            if item['codigo']:
                produtos[item['codigo']] = item
                
    for codigo, nome in participantes.items():
        movimento.append(registro('0150', codigo, nome, '1058', codigo, '', '', '', '', '', '', '', ''))
        
    for codigo, item in produtos.items():
        movimento.append(registro('0200', codigo, item['descricao'], '', '', item['unidade'],
                                  '00', item['ncm'], '', '', '', '0', ''))
                                  
    documentos = []
    for nota in notas:
        documentos.append(registro(
            'C100', nota['ind_oper'], nota['ind_emit'], nota['cod_part'], nota['mod'], '00',
            nota['serie'], nota['numero'], nota['chave'], nota['data'], nota['data'],
            valor_sped(nota['valor']), '9', valor_sped(nota['desconto']), '0,00',
            valor_sped(nota['mercadoria']), '9', valor_sped(nota['frete']),
            valor_sped(nota['seguro']), valor_sped(nota['outros']), valor_sped(nota['bc_icms']),
            valor_sped(nota['icms']), '0,00', '0,00', '0,00', '0,00', '0,00', '0,00', '0,00'))
            
        resumo = {}
        for item in nota['itens']:
            tributacao = tributacao_c170(item)
            
            # C170 Corrigido com posições, zeros e tipagens precisas
            documentos.append(registro(
                'C170', 
                item['numero'], item['codigo'], '', quantidade_sped(item['quantidade']), item['unidade'],
                valor_sped(item['valor']), valor_sped(item['desconto']), '0', tributacao['cst'].zfill(3),
                tributacao['cfop'], '', tributacao['bc_icms'], tributacao['aliquota'],
                tributacao['icms'], '0,00', '0,00', '0,00', 
                '0',     # 19 IND_APUR 
                '99',    # 20 CST_IPI
                '999',   # 21 COD_ENQ 
                '0,00',  # 22 VL_BC_IPI
                '0,00',  # 23 ALIQ_IPI
                '0,00',  # 24 VL_IPI
                '99',    # 25 CST_PIS 
                '0,00',  # 26 VL_BC_PIS
                '0,00',  # 27 ALIQ_PIS (Perc)
                '0,000', # 28 QUANT_BC_PIS
                '0,0000',# 29 ALIQ_PIS (Reais)
                '0,00',  # 30 VL_PIS
                '99',    # 31 CST_COFINS 
                '0,00',  # 32 VL_BC_COFINS
                '0,00',  # 33 ALIQ_COFINS (Perc)
                '0,000', # 34 QUANT_BC_COFINS
                '0,0000',# 35 ALIQ_COFINS (Reais)
                '0,00',  # 36 VL_COFINS
                '',      # 37 COD_CTA
                '0,00'   # 38 VL_ABAT_NT
            ))
            
            chave = (tributacao['cst'].zfill(3), tributacao['cfop'], tributacao['aliquota'])
            grupo = resumo.setdefault(chave, [0.0, 0.0, 0.0])
            grupo[0] += float(item['valor'].replace(',', '.') or 0)
            grupo[1] += float(tributacao['bc_icms'].replace(',', '.') or 0)
            grupo[2] += float(tributacao['icms'].replace(',', '.') or 0)
            
        for (cst, cfop, aliquota), valores in resumo.items():
            documentos.append(registro('C190', cst, cfop, valor_sped(aliquota),
                                       valor_sped(str(valores[0])), valor_sped(str(valores[1])),
                                       valor_sped(str(valores[2])), '0,00', '0,00', '0', '0,00', ''))
    return movimento, documentos

def nome_seguro(valor):
    return re.sub(r'[^A-Za-z0-9]+', '_', valor).strip('_').upper() or 'EMPRESA'

def validar_dados(dados):
    obrigatorios = {
        'razao_social': 'Razão social', 'cnpj': 'CNPJ', 'ie': 'Inscrição estadual', 'uf': 'UF',
        'municipio': 'Código do município', 'data_inicio': 'Data inicial',
        'data_fim': 'Data final',
    }
    faltantes = [nome for chave, nome in obrigatorios.items() if not dados.get(chave)]
    if faltantes:
        raise ValueError('Preencha: ' + ', '.join(faltantes) + '.')
        
    dados['cnpj'] = somente_digitos(dados['cnpj'])
    if len(dados['cnpj']) != 14:
        raise ValueError('CNPJ deve conter 14 dígitos.')
        
    dados['uf'] = dados['uf'].upper().strip()
    if len(dados['uf']) != 2:
        raise ValueError('UF deve conter duas letras, por exemplo CE.')
        
    dados['municipio'] = somente_digitos(dados['municipio'])
    if len(dados['municipio']) != 7:
        raise ValueError('Código do município deve conter 7 dígitos (IBGE).')
        
    dados['data_inicio'] = data_efd(dados['data_inicio'], 'Data inicial')
    dados['data_fim'] = data_efd(dados['data_fim'], 'Data final')
    if datetime.strptime(dados['data_inicio'], '%d%m%Y') > datetime.strptime(dados['data_fim'], '%d%m%Y'):
        raise ValueError('Data inicial não pode ser posterior à data final.')

def gerar_efd(dados, caminhos_xml=None):
    validar_dados(dados)
    notas = ler_xmls(caminhos_xml)
    movimento, documentos = gerar_registros_notas(notas)
    
    linhas = [
        # Correção no 0000: O campo 8 (CPF) da empresa deve ser vazio se CNPJ preenchido
        registro('0000', '020', '0', dados['data_inicio'], dados['data_fim'], dados['razao_social'],
                 dados['cnpj'], '', dados['uf'], dados.get('ie'),
                 dados['municipio'], dados.get('im'), dados.get('suframa'),
                 dados.get('perfil', 'B'), dados.get('atividade', '1')),
        registro('0001', '0'),
        registro('0005', dados['razao_social'], dados.get('cep'), dados.get('endereco'),
                 dados.get('numero'), dados.get('complemento'), dados.get('bairro'),
                 dados.get('telefone'), '', dados.get('email')),
        registro('0100', dados.get('nome_contador'), dados.get('cpf_contador'), dados.get('crc'),
                 dados.get('cnpj_contador'), dados.get('cep_contador'), dados.get('endereco_contador'),
                 dados.get('numero_contador'), '', dados.get('bairro_contador'),
                 dados.get('telefone_contador'), '', dados.get('email_contador'), dados['municipio']),
    ]
    linhas.extend(movimento)
    linhas.append(registro('0990', len(linhas) + 1))
    
    linhas.extend((registro('B001', '1'), registro('B990', '2'),
                   registro('C001', '0' if documentos else '1')))
    linhas.extend(documentos)
    
    linhas.extend((registro('C990', str(2 + len(documentos))), registro('D001', '1'),
                   registro('D990', '2'), registro('E001', '0'), registro('E990', '2'),
                   registro('G001', '1'), registro('G990', '2'), registro('H001', '1'),
                   registro('H990', '2'), registro('K001', '1'), registro('K990', '2'),
                   registro('1001', '0'), registro('1990', '2'), registro('9001', '0')))
                   
    codigos = [linha.split('|')[1] for linha in linhas]
    contagem = {codigo: codigos.count(codigo) for codigo in set(codigos)}
    codigos_9900 = set(contagem) | {'9900', '9990', '9999'}
    
    linhas.extend(registro('9900', codigo, contagem.get(codigo, 1))
                  for codigo in sorted(codigos_9900) if codigo != '9900')
                  
    quantidade_9900 = len(codigos_9900)
    linhas.append(registro('9900', '9900', quantidade_9900))
    indice_9001 = next(indice for indice, linha in enumerate(linhas) if '|9001|' in linha)
    quantidade_9990 = len(linhas) - indice_9001 + 1
    linhas.append(registro('9990', quantidade_9990))
    linhas.append(registro('9999', len(linhas) + 1))
    
    return '\n'.join(linhas) + '\n'

def gerar_arquivo(dados, caminhos_xml=None):
    conteudo = gerar_efd(dados, caminhos_xml)
    os.makedirs(PASTA_SAIDA, exist_ok=True)
    periodo = f'{dados["data_inicio"][2:4]}_{dados["data_inicio"][4:]}'
    caminho = os.path.join(PASTA_SAIDA, f'{nome_seguro(dados["razao_social"])}-SPED_FISCAL_{periodo}.txt')
    with open(caminho, 'w', encoding='utf-8', newline='') as arquivo:
        arquivo.write(conteudo)
    return caminho

def criar_interface():
    janela = tk.Tk()
    icone_path = resolve_asset_path('app.ico')
    if os.path.exists(icone_path):
        try:
            janela.iconbitmap(default=icone_path)
        except tk.TclError:
            pass

    janela.title('GenTXT')
    janela.geometry('900x760')
    janela.minsize(760, 620)
    janela.resizable(True, True)
    janela.configure(bg='#292f36')
    estilo = ttk.Style(janela)
    if 'clam' in estilo.theme_names():
        estilo.theme_use('clam')
    estilo.configure('GenTXT.TFrame', background='#303740')
    estilo.configure('GenTXT.TLabel', background='#303740', foreground='#e5e9ef', font=('Segoe UI', 10))
    estilo.configure('GenTXT.TLabelframe', background='#39424d', bordercolor='#56616d', relief='solid')
    estilo.configure(
        'GenTXT.TLabelframe.Label', background='#39424d', foreground='#f0f3f6',
        font=('Segoe UI', 11, 'bold')
    )
    estilo.configure(
        'GenTXT.TEntry', padding=(8, 7), fieldbackground='#262c33',
        foreground='#f0f3f6', insertcolor='#f0f3f6'
    )
    estilo.map('GenTXT.TEntry', fieldbackground=[('focus', '#303740')])
    estilo.configure(
        'GenTXT.TButton', font=('Segoe UI', 10), padding=(12, 8),
        background='#48535f', foreground='#f0f3f6'
    )
    estilo.map(
        'GenTXT.TButton', background=[('active', '#596674'), ('disabled', '#353d46')],
        foreground=[('disabled', '#89939e')]
    )
    estilo.configure(
        'GenTXT.Primary.TButton', font=('Segoe UI', 10, 'bold'), padding=(16, 9),
        background='#34798b', foreground='#ffffff'
    )
    estilo.map('GenTXT.Primary.TButton', background=[('active', '#286677')], foreground=[('active', '#ffffff')])
    estilo.configure('GenTXT.Footer.TLabel', background='#252b32', foreground='#d4dae1', font=('Segoe UI', 10))
    estilo.configure(
        'GenTXT.Treeview', background='#303740', fieldbackground='#303740',
        foreground='#e5e9ef', rowheight=28
    )
    estilo.map('GenTXT.Treeview', background=[('selected', '#34798b')])
    estilo.configure(
        'GenTXT.Treeview.Heading', background='#424c57', foreground='#f0f3f6',
        font=('Segoe UI', 10, 'bold'), relief='flat'
    )
    estilo.map('GenTXT.Treeview.Heading', background=[('active', '#505c68')])

    menu = tk.Frame(janela, bg='#292f36', padx=42, pady=34)
    menu.pack(fill='both', expand=True)

    cabecalho_logo = tk.Frame(menu, bg='#292f36')
    cabecalho_logo.pack(anchor='w')
    tk.Label(
        cabecalho_logo, text='GenTXT', bg='#292f36', fg='#f0f3f6',
        font=('Segoe UI', 28, 'bold')
    ).pack(anchor='w')
    tk.Label(
        menu, text='Geradores de arquivos SPED', bg='#292f36', fg='#b1bac4',
        font=('Segoe UI', 12)
    ).pack(anchor='w', pady=(2, 24))
    tk.Label(
        menu, text='Escolha o tipo de arquivo que deseja gerar:',
        bg='#292f36', fg='#e5e9ef', font=('Segoe UI', 12, 'bold')
    ).pack(anchor='w', pady=(0, 14))

    def selecionar_modulo(nome, disponivel):
        if disponivel:
            menu.pack_forget()
            formulario.pack(fill='both', expand=True)
        else:
            messagebox.showinfo(
                nome,
                f'{nome}\n\nEm breve!'
            )

    modulos = [
        ('SPED Contribuições', 'EFD Contribuições • PIS e COFINS', False),
        ('SPED Fiscal ICMS/IPI', 'EFD Fiscal • Gerador disponível', True),
        ('ECF', 'Escrituração Contábil Fiscal • Em breve', False),
        ('ECD', 'Escrituração Contábil Digital • Em breve', False),
    ]
    grade = tk.Frame(menu, bg='#292f36')
    grade.pack(fill='x')
    for indice, (nome, descricao, disponivel) in enumerate(modulos):
        cor_normal = '#39424d' if disponivel else '#323941'
        cor_hover = '#465665' if disponivel else '#383f48'
        botao = tk.Button(
            grade,
            text=f'{nome}\n{descricao}',
            command=lambda modulo=nome, ativo=disponivel: selecionar_modulo(modulo, ativo),
            anchor='w',
            justify='left',
            padx=18,
            pady=16,
            width=34,
            height=3,
            bg=cor_normal,
            fg='#f0f3f6' if disponivel else '#a2abb5',
            activebackground='#34798b',
            activeforeground='#ffffff',
            font=('Segoe UI', 11, 'bold'),
            relief='solid',
            bd=1,
            cursor='hand2',
        )
        botao.grid(row=indice // 2, column=indice % 2, padx=7, pady=7, sticky='nsew')
        botao.bind(
            '<Enter>',
            lambda _, alvo=botao, cor=cor_hover: alvo.configure(background=cor)
        )
        botao.bind(
            '<Leave>',
            lambda _, alvo=botao, cor=cor_normal: alvo.configure(background=cor)
        )
    grade.grid_columnconfigure(0, weight=1)
    grade.grid_columnconfigure(1, weight=1)
    tk.Label(
        menu, text='Os módulos marcados como “Em breve” ainda não geram arquivos.',
        bg='#292f36', fg='#a2abb5', font=('Segoe UI', 9)
    ).pack(anchor='w', pady=(18, 0))
    links = tk.Frame(menu, bg='#292f36')
    links.pack(anchor='w', pady=(14, 0))
    for indice, (nome, url) in enumerate((
        ('GitHub', 'https://github.com/AlbuquerqueGabriel22'),
        ('LinkedIn', 'https://www.linkedin.com/in/gabriel-albuquerque-072641332/'),
    )):
        if indice:
            tk.Label(links, text='•', bg='#292f36', fg='#a2abb5').pack(side='left', padx=8)
        link = tk.Label(
            links, text=nome, bg='#292f36', fg='#72c7df',
            font=('Segoe UI', 10, 'underline'), cursor='hand2'
        )
        link.pack(side='left')
        link.bind(
            '<Button-1>', lambda _, endereco=url: webbrowser.open(endereco, new=2)
        )

    formulario = ttk.Frame(janela, style='GenTXT.TFrame')
    formulario.grid_columnconfigure(0, weight=1)
    formulario.grid_rowconfigure(1, weight=1)

    cabecalho = tk.Frame(formulario, bg='#252b32', padx=24, pady=14)
    cabecalho.grid(row=0, column=0, sticky='ew')
    cabecalho.grid_columnconfigure(1, weight=1)
    ttk.Button(
        cabecalho, text='←  Menu principal',
        command=lambda: (formulario.pack_forget(), menu.pack(fill='both', expand=True)),
        style='GenTXT.TButton'
    ).grid(row=0, column=0, rowspan=3, sticky='w', padx=(0, 20))
    tk.Label(
        cabecalho, text='SPED Fiscal ICMS/IPI', bg='#252b32', fg='#f0f3f6',
        font=('Segoe UI', 17, 'bold')
    ).grid(row=0, column=1, sticky='w')
    tk.Label(
        cabecalho, text='Preencha os dados da escrituração e gere seu arquivo.',
        bg='#252b32', fg='#b1bac4', font=('Segoe UI', 10)
    ).grid(row=1, column=1, sticky='w', pady=(2, 0))
    indicadores_obrigatorios = tk.Frame(cabecalho, bg='#252b32')
    indicadores_obrigatorios.grid(row=2, column=1, sticky='w', pady=(6, 0))
    status_obrigatorios = tk.Label(
        indicadores_obrigatorios, text='Obrigatórios: 0/7', bg='#252b32',
        fg='#d4dae1', font=('Segoe UI', 9)
    )
    status_obrigatorios.pack(side='left')
    progresso_obrigatorios = ttk.Progressbar(
        indicadores_obrigatorios, maximum=7, length=180, mode='determinate'
    )
    progresso_obrigatorios.pack(side='left', padx=(12, 0))

    area = ttk.Frame(formulario, style='GenTXT.TFrame', padding=(24, 14, 24, 10))
    area.grid(row=1, column=0, sticky='nsew')
    area.grid_columnconfigure(0, weight=1)
    area.grid_rowconfigure(0, weight=1)
    tela = tk.Canvas(area, bg='#303740', highlightthickness=0)
    barra = ttk.Scrollbar(area, orient='vertical', command=tela.yview)
    tela.configure(yscrollcommand=barra.set)
    tela.grid(row=0, column=0, sticky='nsew')
    barra.grid(row=0, column=1, sticky='ns', padx=(8, 0))
    conteudo_formulario = ttk.Frame(tela, style='GenTXT.TFrame')
    janela_conteudo = tela.create_window((0, 0), window=conteudo_formulario, anchor='nw')
    conteudo_formulario.bind(
        '<Configure>', lambda _: tela.configure(scrollregion=tela.bbox('all'))
    )
    tela.bind(
        '<Configure>', lambda evento: tela.itemconfigure(janela_conteudo, width=evento.width)
    )

    rodape = tk.Frame(formulario, bg='#252b32', padx=24, pady=12)
    rodape.grid(row=2, column=0, sticky='ew')
    rodape.grid_columnconfigure(1, weight=1)
    campos = {}
    variaveis_campos = {}
    xmls_selecionados = []
    chaves_obrigatorias = (
        'razao_social', 'cnpj', 'ie', 'uf', 'municipio', 'data_inicio', 'data_fim'
    )

    def atualizar_progresso(*_):
        quantidade = sum(
            bool(variaveis_campos[chave].get().strip())
            for chave in chaves_obrigatorias if chave in variaveis_campos
        )
        progresso_obrigatorios.configure(value=quantidade)
        status_obrigatorios.configure(
            text=f'Obrigatórios: {quantidade}/{len(chaves_obrigatorias)}'
            + (' • Campos preenchidos' if quantidade == len(chaves_obrigatorias) else ''),
            fg='#7ed3aa' if quantidade == len(chaves_obrigatorias) else '#d4dae1'
        )
    
    grupos = [
        ('Dados da empresa', [
            ('razao_social', 'Razão social *'), ('cnpj', 'CNPJ *'), ('ie', 'Inscrição estadual *'),
            ('uf', 'UF *'), ('municipio', 'Código município *'), ('im', 'Inscrição municipal'),
            ('cep', 'CEP'), ('endereco', 'Endereço'), ('numero', 'Número'),
            ('complemento', 'Complemento'), ('bairro', 'Bairro'), ('telefone', 'Telefone'),
            ('email', 'E-mail'),
        ]),
        ('Período e configuração', [
            ('data_inicio', 'Data inicial *'), ('data_fim', 'Data final *'),
            ('perfil', 'Perfil (A/B/C)'), ('atividade', 'Indicador atividade'),
        ]),
        ('Contador', [
            ('nome_contador', 'Nome do contador'), ('cpf_contador', 'CPF contador'), ('crc', 'CRC'),
            ('cnpj_contador', 'CNPJ contador'), ('cep_contador', 'CEP contador'),
            ('endereco_contador', 'Endereço contador'), ('numero_contador', 'Número contador'),
            ('bairro_contador', 'Bairro contador'), ('telefone_contador', 'Telefone contador'),
            ('email_contador', 'E-mail contador'),
        ]),
    ]
    
    for titulo, itens in grupos:
        secao = ttk.LabelFrame(
            conteudo_formulario, text=titulo, style='GenTXT.TLabelframe',
            padding=(16, 12)
        )
        secao.pack(fill='x', pady=(0, 12))
        secao.grid_columnconfigure(1, weight=1)
        secao.grid_columnconfigure(3, weight=1)
        for indice, (chave, rotulo) in enumerate(itens):
            linha = indice // 2
            coluna = (indice % 2) * 2
            ttk.Label(secao, text=rotulo, style='GenTXT.TLabel').grid(
                row=linha, column=coluna, sticky='w', padx=(0, 8), pady=6
            )
            variavel = tk.StringVar()
            entrada = ttk.Entry(
                secao, width=24, style='GenTXT.TEntry', textvariable=variavel
            )
            entrada.grid(row=linha, column=coluna + 1, sticky='ew', padx=(0, 14), pady=5)
            campos[chave] = entrada
            variaveis_campos[chave] = variavel
            variavel.trace_add('write', atualizar_progresso)
        
    campos['perfil'].insert(0, 'B')
    campos['atividade'].insert(0, '1')
    atualizar_progresso()

    xml_status = ttk.Label(
        rodape, text='Nenhuma NF-e XML selecionada (opcional).', style='GenTXT.Footer.TLabel'
    )
    xml_status.grid(row=0, column=1, sticky='w', padx=12)

    def selecionar_xmls():
        novos_xmls = filedialog.askopenfilenames(
            title='Selecione os XMLs das NF-e',
            filetypes=[('Arquivos XML', '*.xml'), ('Todos os arquivos', '*.*')]
        )
        chaves_caminhos = {
            os.path.normcase(os.path.abspath(caminho))
            for caminho in xmls_selecionados
        }
        for caminho in novos_xmls:
            chave_caminho = os.path.normcase(os.path.abspath(caminho))
            if chave_caminho not in chaves_caminhos:
                xmls_selecionados.append(caminho)
                chaves_caminhos.add(chave_caminho)

        quantidade = len(xmls_selecionados)
        xml_status.configure(text=f'{quantidade} NF-e XML selecionada(s).')
        botao_ver_xmls.configure(state='normal' if quantidade else 'disabled')

    def ver_xmls():
        if not xmls_selecionados:
            messagebox.showinfo('XMLs selecionados', 'Selecione os arquivos XML primeiro.', parent=janela)
            return

        janela_xmls = tk.Toplevel(janela)
        janela_xmls.title('XMLs selecionados')
        janela_xmls.geometry('1080x500')
        janela_xmls.minsize(760, 400)
        janela_xmls.configure(bg='#303740')
        janela_xmls.transient(janela)
        janela_xmls.grid_columnconfigure(0, weight=1)
        janela_xmls.grid_rowconfigure(1, weight=1)

        resumo_xmls = ttk.Label(
            janela_xmls,
            text=f'Arquivos XML selecionados: {len(xmls_selecionados)}',
            style='GenTXT.TLabel'
        )
        resumo_xmls.grid(row=0, column=0, sticky='w', padx=18, pady=(16, 10))

        lista = ttk.Treeview(
            janela_xmls, columns=('arquivo', 'data', 'valor', 'chave'), show='headings',
            style='GenTXT.Treeview', selectmode='extended'
        )
        lista.heading('arquivo', text='Arquivo')
        lista.heading('data', text='Data de emissão')
        lista.heading('valor', text='Valor da NF-e')
        lista.heading('chave', text='Chave de acesso (44 dígitos)')
        lista.column('arquivo', width=210, minwidth=150, anchor='w')
        lista.column('data', width=110, minwidth=95, anchor='center')
        lista.column('valor', width=130, minwidth=110, anchor='e')
        lista.column('chave', width=380, minwidth=300, anchor='w')
        lista.grid(row=1, column=0, sticky='nsew', padx=(18, 0), pady=(0, 14))
        barra_xmls = ttk.Scrollbar(janela_xmls, orient='vertical', command=lista.yview)
        barra_xmls.grid(row=1, column=1, sticky='ns', padx=(0, 18), pady=(0, 14))
        barra_xmls_horizontal = ttk.Scrollbar(
            janela_xmls, orient='horizontal', command=lista.xview
        )
        barra_xmls_horizontal.grid(
            row=2, column=0, sticky='ew', padx=18, pady=(0, 12)
        )
        lista.configure(
            yscrollcommand=barra_xmls.set,
            xscrollcommand=barra_xmls_horizontal.set
        )
        lista.tag_configure('invalido', foreground='#ff9c9c')

        dados_por_caminho = {}
        caminhos_por_item = {}
        for indice, caminho in enumerate(xmls_selecionados):
            try:
                nota = ler_nfe(caminho)
                dados_por_caminho[caminho] = nota
                data_emissao = (
                    datetime.strptime(nota['data'], '%d%m%Y').strftime('%d/%m/%Y')
                    if nota['data'] else 'Não informada'
                )
                valor_nota = (
                    f'R$ {valor_sped(nota["valor"])}'
                    if nota['valor'] else 'Não informado'
                )
                chave_acesso = nota['chave'] or 'Não informada'
                tags = ()
            except (ET.ParseError, OSError, ValueError) as erro_xml:
                dados_por_caminho[caminho] = {'erro': str(erro_xml)}
                data_emissao = 'XML inválido'
                valor_nota = '—'
                chave_acesso = 'Não foi possível ler'
                tags = ('invalido',)

            identificador = str(indice)
            caminhos_por_item[identificador] = caminho
            lista.insert(
                '', 'end', iid=identificador,
                values=(
                    os.path.basename(caminho), data_emissao, valor_nota, chave_acesso
                ),
                tags=tags
            )

        detalhes_xml = ttk.Label(
            janela_xmls, text='Selecione uma NF-e para ver os detalhes.',
            style='GenTXT.TLabel', wraplength=1000
        )
        detalhes_xml.grid(row=3, column=0, columnspan=2, sticky='ew', padx=18, pady=(0, 12))

        def atualizar_detalhes(_=None):
            selecionados = lista.selection()
            if not selecionados:
                detalhes_xml.configure(text='Selecione uma NF-e para ver os detalhes.')
                botao_copiar_chave.configure(state='disabled')
                return

            caminho = caminhos_por_item[selecionados[0]]
            nota = dados_por_caminho[caminho]
            if 'erro' in nota:
                detalhes_xml.configure(
                    text=f'Não foi possível ler {os.path.basename(caminho)}: {nota["erro"]}'
                )
                botao_copiar_chave.configure(state='disabled')
                return

            detalhes_xml.configure(
                text=(
                    f'NF-e {nota["numero"] or "—"} • Série {nota["serie"] or "—"}'
                    f' • Participante: {nota["nome_part"] or "Não informado"}'
                    f' • Chave: {nota["chave"] or "Não informada"}'
                )
            )
            botao_copiar_chave.configure(
                state='normal' if nota['chave'] else 'disabled'
            )

        def copiar_chave():
            selecionados = lista.selection()
            if not selecionados:
                return
            caminho = caminhos_por_item[selecionados[0]]
            chave_acesso = dados_por_caminho[caminho].get('chave')
            if chave_acesso:
                janela_xmls.clipboard_clear()
                janela_xmls.clipboard_append(chave_acesso)
                detalhes_xml.configure(text='Chave de acesso copiada para a área de transferência.')

        def excluir_xmls_selecionados():
            itens_removidos = lista.selection()
            caminhos_removidos = {caminhos_por_item[item] for item in itens_removidos}
            xmls_selecionados[:] = [
                caminho for caminho in xmls_selecionados
                if caminho not in caminhos_removidos
            ]
            for item in itens_removidos:
                lista.delete(item)

            quantidade = len(xmls_selecionados)
            resumo_xmls.configure(text=f'Arquivos XML selecionados: {quantidade}')
            xml_status.configure(
                text=f'{quantidade} NF-e XML selecionada(s).'
                if quantidade else 'Nenhuma NF-e XML selecionada (opcional).'
            )
            botao_ver_xmls.configure(state='normal' if quantidade else 'disabled')
            botao_excluir.configure(state='disabled')
            atualizar_detalhes()

        botao_excluir = ttk.Button(
            janela_xmls, text='Excluir selecionado(s)',
            command=excluir_xmls_selecionados, style='GenTXT.TButton', state='disabled'
        )
        botao_excluir.grid(row=4, column=0, sticky='w', padx=18, pady=(0, 16))
        botao_copiar_chave = ttk.Button(
            janela_xmls, text='Copiar chave de acesso', command=copiar_chave,
            style='GenTXT.TButton', state='disabled'
        )
        botao_copiar_chave.grid(row=4, column=0, sticky='w', padx=(190, 0), pady=(0, 16))
        lista.bind(
            '<<TreeviewSelect>>', atualizar_detalhes
        )
        ttk.Button(
            janela_xmls, text='Fechar', command=janela_xmls.destroy,
            style='GenTXT.TButton'
        ).grid(row=4, column=0, sticky='e', padx=18, pady=(0, 16))
        lista.bind(
            '<<TreeviewSelect>>',
            lambda _: botao_excluir.configure(
                state='normal' if lista.selection() else 'disabled'
            ), add='+'
        )

    def gerar():
        dados = {chave: entrada.get().strip() for chave, entrada in campos.items()}
        try:
            caminho = gerar_arquivo(dados, xmls_selecionados)
            texto_xml = f'{len(xmls_selecionados)} NF-e(s) importada(s).' if xmls_selecionados else 'Nenhuma NF-e XML foi importada.'
            messagebox.showinfo('GenTXT - EFD gerada', f'Arquivo criado:\n\n{caminho}\n\n'
                                              f'{texto_xml}\n\nConfira o arquivo no PVA antes da transmissão.')
        except (OSError, ValueError) as exc:
            messagebox.showerror('Não foi possível gerar', str(exc))

    ttk.Button(
        rodape, text='Selecionar XMLs', command=selecionar_xmls, style='GenTXT.TButton'
    ).grid(row=0, column=0, sticky='w')
    botao_ver_xmls = ttk.Button(
        rodape, text='Ver XMLs', command=ver_xmls, style='GenTXT.TButton', state='disabled'
    )
    botao_ver_xmls.grid(row=0, column=0, sticky='w', padx=(150, 0))
    ttk.Button(
        rodape, text='Gerar arquivo SPED Fiscal', command=gerar,
        style='GenTXT.Primary.TButton'
    ).grid(row=0, column=2, sticky='e')
    ttk.Label(
        rodape, text='Saída: downloads/arquivos  •  * Campos obrigatórios',
        style='GenTXT.Footer.TLabel'
    ).grid(row=1, column=0, columnspan=3, sticky='w', pady=(9, 0))
    janela.mainloop()

if __name__ == '__main__':
    criar_interface()