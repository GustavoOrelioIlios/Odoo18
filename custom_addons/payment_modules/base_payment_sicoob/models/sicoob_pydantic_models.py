# -*- coding: utf-8 -*-

from typing import Optional, List, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import date, datetime
from decimal import Decimal
import re

def format_decimal_to_str(value: Union[float, Decimal], total_digits: int, decimal_places: int) -> str:
    if value is None:
        return ""
    d_value = Decimal(str(value))
    scaled_value = int(d_value * (10 ** decimal_places))
    return f"{scaled_value:0{total_digits}d}"

class PagadorModel(BaseModel):
    """Modelo Pydantic para dados do pagador"""
    numeroCpfCnpj: str = Field(..., description="CPF/CNPJ do pagador")
    nome: str = Field(..., description="Nome do pagador")
    endereco: str = Field(..., description="Endereço do pagador")
    bairro: str = Field(..., description="Bairro do pagador")
    cidade: str = Field(..., description="Cidade do pagador")
    cep: str = Field(..., description="CEP do pagador")
    uf: str = Field(..., description="UF do pagador")
    email: Optional[str] = Field(None, description="E-mail do pagador")

    model_config = ConfigDict(populate_by_name=True, extra='forbid', str_strip_whitespace=True)

class BeneficiarioFinalModel(BaseModel):
    """Modelo Pydantic para dados do beneficiário final"""
    numeroCpfCnpj: str = Field(..., description="CPF/CNPJ do beneficiário final")
    nome: str = Field(..., description="Nome do beneficiário final")

    model_config = ConfigDict(populate_by_name=True, extra='forbid', str_strip_whitespace=True)

class RateioCreditosItemModel(BaseModel):
    """Modelo Pydantic para item de rateio de créditos"""
    numeroBanco: int = Field(..., description="Número do banco")
    numeroAgencia: int = Field(..., description="Número da agência")
    numeroContaCorrente: int = Field(..., description="Número da conta corrente")
    valor: float = Field(..., description="Valor do rateio")

    model_config = ConfigDict(populate_by_name=True, extra='forbid', str_strip_whitespace=True)

class SicoobBoletoRequestPayload(BaseModel):
    """Modelo Pydantic principal para requisição de boleto Sicoob"""
    # Campos obrigatórios conforme especificação
    dataEmissao: str = Field(
        ..., 
        description="Data de emissão do boleto. Caso não seja informado, o sistema atribui a data de registro do boleto no Sisbr. Formato: yyyy-MM-dd"
    )
    nossoNumero: int = Field(
        ..., 
        description="Número que identifica o boleto de cobrança no Sisbr. Gerado pela sequência do Odoo."
    )
    seuNumero: str = Field(
        ..., 
        description="Número identificador do boleto no sistema do beneficiário (número da fatura). Tamanho máximo 18"
    )
    valor: float = Field(
        ..., 
        gt=0, 
        description="Valor nominal do boleto"
    )
    dataVencimento: str = Field(
        ..., 
        description="Data de vencimento do boleto. Formato: yyyy-MM-dd"
    )
    dataLimitePagamento: str = Field(
        ..., 
        description="Data limite para pagamento do boleto. Formato: yyyy-MM-dd"
    )
    aceite: bool = Field(
        True, 
        description="Identificador do aceite do boleto"
    )
    codigoEspecieDocumento: str = Field(
        ..., 
        description="Espécie do Documento. Ex: DM (Duplicata Mercantil), DS (Duplicata de Serviço), etc."
    )
    
    # Campos adicionais necessários para o Sicoob
    numeroCliente: int = Field(..., description="Número do cliente no Sicoob")
    codigoModalidade: int = Field(..., description="Código da modalidade de cobrança")
    numeroContaCorrente: int = Field(..., description="Número da conta corrente")
    pagador: PagadorModel = Field(..., description="Dados do pagador")
    beneficiarioFinal: Optional[BeneficiarioFinalModel] = Field(None, description="Dados do beneficiário final")
    
    # Campos opcionais para configurações adicionais
    mensagensInstrucao: Optional[List[str]] = Field(None, description="Mensagens de instrução")
    numeroContratoCobranca: Optional[int] = Field(None, description="Número do contrato de cobrança")
    
    # ADICIONADO: Novos campos de identificação
    identificacaoBoletoEmpresa: Optional[str] = Field(None, description="Campo para uso da empresa do beneficiário para identificação do boleto")
    identificacaoEmissaoBoleto: Optional[int] = Field(None, description="1 – Banco Emite, 2 – Cliente Emite")
    identificacaoDistribuicaoBoleto: Optional[int] = Field(None, description="1 – Banco Distribui, 2 – Cliente Distribui")
    gerarPdf: Optional[bool] = Field(None, description="Define se o PDF do boleto deve ser gerado")

    # Campos de juros
    tipoJurosMora: Optional[int] = Field(None, description="Tipo de juros de mora")
    valorJurosMora: Optional[float] = Field(None, description="Valor ou percentual dos juros de mora")
    dataJurosMora: Optional[str] = Field(None, description="Data de início dos juros de mora")

    # Campos de multa
    tipoMulta: Optional[int] = Field(None, description="Tipo de multa")
    valorMulta: Optional[float] = Field(None, description="Valor da multa quando tipo for valor fixo")
    percentualMulta: Optional[float] = Field(None, description="Percentual da multa quando tipo for percentual")
    dataMulta: Optional[str] = Field(None, description="Data de início da multa")

    # ALTERADO: Campo tipoDesconto agora é obrigatório
    tipoDesconto: int = Field(..., description="Tipo de desconto (0=Sem desconto, 1=Valor fixo, 2=Percentual)")
    dataPrimeiroDesconto: Optional[str] = Field(None, description="Data do primeiro desconto")
    valorPrimeiroDesconto: Optional[float] = Field(None, description="Valor ou percentual do primeiro desconto")

    # ADICIONADO: Campo numeroParcela obrigatório
    numeroParcela: int = Field(..., description="Número da parcela do boleto")

    # ADICIONADO: Campo para PIX
    codigoCadastrarPIX: Optional[int] = Field(None, description="Código para cadastrar PIX (0=Não gerar, 1=Gerar)")

    model_config = ConfigDict(populate_by_name=True, extra='forbid', str_strip_whitespace=True)

    @field_validator('dataEmissao', 'dataVencimento', 'dataLimitePagamento', 'dataJurosMora', 'dataMulta', 'dataPrimeiroDesconto')
    def validate_date(cls, v):
        """Valida e formata as datas"""
        if isinstance(v, date):
            return v.isoformat()
        return v

    @field_validator('seuNumero')
    def validate_seu_numero(cls, v):
        """Valida o tamanho do seu número"""
        if len(v) > 18:
            raise ValueError("seuNumero não pode ter mais de 18 caracteres")
        return v

    @field_validator('codigoEspecieDocumento')
    def validate_especie_documento(cls, v):
        """Valida o código da espécie do documento"""
        especies_validas = {
            'CH': 'Cheque',
            'DM': 'Duplicata Mercantil',
            'DMI': 'Duplicata Mercantil p/ Indicação',
            'DS': 'Duplicata de Serviço',
            'DSI': 'Duplicata de Serviço p/ Indicação',
            'DR': 'Duplicata Rural',
            'LC': 'Letra de Câmbio',
            'NCC': 'Nota de Crédito Comercial',
            'NCE': 'Nota de Crédito a Exportação',
            'NCI': 'Nota de Crédito Industrial',
            'NCR': 'Nota de Crédito Rural',
            'NP': 'Nota Promissória',
            'NPR': 'Nota Promissória Rural',
            'TM': 'Triplicata Mercantil',
            'TS': 'Triplicata de Serviço',
            'NS': 'Nota de Seguro',
            'RC': 'Recibo',
            'FAT': 'Fatura',
            'ND': 'Nota de Débito',
            'AP': 'Apólice de Seguro',
            'ME': 'Mensalidade Escolar',
            'PC': 'Parcela de Consórcio',
            'NF': 'Nota Fiscal',
            'DD': 'Documento de Dívida',
            'CPR': 'Cédula de Produto Rural',
            'WR': 'Warrant',
            'DAE': 'Dívida Ativa de Estado',
            'DAM': 'Dívida Ativa de Município',
            'DAU': 'Dívida Ativa da União',
            'EC': 'Encargos Condominiais',
            'CPS': 'Conta de Prestação de Serviços',
            'OUT': 'Outros'
        }
        if v not in especies_validas:
            raise ValueError(f"Espécie de documento inválida. Valores válidos: {', '.join(especies_validas.keys())}")
        return v

class SicoobBoletoValidator:
    """Classe utilitária para validação de dados do boleto Sicoob"""
    
    @staticmethod
    def validar_payload(dados: dict) -> tuple[bool, dict, str]:
        """
        Valida os dados do boleto usando os modelos Pydantic
        
        Args:
            dados (dict): Dicionário com os dados do boleto
            
        Returns:
            tuple: (sucesso, dados_validados, mensagem)
                - sucesso (bool): True se a validação foi bem sucedida
                - dados_validados (dict): Dados validados e formatados pelo Pydantic
                - mensagem (str): Mensagem de erro em caso de falha
        """
        try:
            modelo = SicoobBoletoRequestPayload(**dados)
            return True, modelo.model_dump(exclude_none=True), ""
        except Exception as e:
            erros = []
            for error in e.errors():
                campo = " -> ".join(str(loc) for loc in error['loc'])
                msg = error['msg']
                
                # Mapeamento de mensagens de erro comuns
                if "field required" in msg:
                    msg = f"Campo obrigatório"
                elif "must be greater than" in msg:
                    msg = f"Deve ser maior que zero"
                elif "invalid date format" in msg:
                    msg = f"Formato de data inválido"
                elif "string does not match pattern" in msg:
                    if "CPF" in campo or "CNPJ" in campo:
                        msg = "CPF/CNPJ inválido"
                    elif "CEP" in campo:
                        msg = "CEP deve conter 8 dígitos"
                    elif "UF" in campo:
                        msg = "UF deve ser 2 letras maiúsculas"
                    elif "email" in campo:
                        msg = "E-mail inválido"
                
                erros.append(f"Campo '{campo}': {msg}")
            
            return False, {}, "\n".join(erros)

    @staticmethod
    def formatar_erros_para_exibicao(erros: str) -> str:
        """
        Formata os erros de validação para exibição ao usuário
        
        Args:
            erros (str): String com os erros de validação
            
        Returns:
            str: Erros formatados para exibição
        """
        if not erros:
            return ""
        
        return "Erros de validação encontrados:\n" + erros 