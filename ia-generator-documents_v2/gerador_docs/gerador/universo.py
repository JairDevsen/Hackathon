"""Universo fictício coerente: empresas, empregados, competências e o mês trabalhado de cada um."""
from __future__ import annotations

import calendar
import random
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from faker import Faker

SEGMENTOS = {
    "Limpeza e Conservação": [("Auxiliar de Limpeza", 1650, 1900), ("Servente", 1600, 1800), ("Encarregado de Limpeza", 2300, 2800)],
    "Vigilância Patrimonial": [("Vigilante", 2400, 3100), ("Supervisor de Vigilância", 3300, 4200)],
    "Manutenção Predial": [("Eletricista", 2600, 3400), ("Auxiliar de Manutenção", 1800, 2200), ("Bombeiro Hidráulico", 2400, 3000)],
    "Portaria e Recepção": [("Porteiro", 1700, 2000), ("Recepcionista", 1750, 2100)],
    "Copa e Cozinha": [("Copeira", 1650, 1850), ("Cozinheira", 2000, 2400)],
}
CIDADES_PE = [("Recife", 50000, 52999), ("Olinda", 53000, 53199), ("Jaboatão dos Guararapes", 54000, 54499),
              ("Paulista", 53400, 53499), ("Caruaru", 55000, 55099), ("Garanhuns", 55290, 55299), ("Arcoverde", 56500, 56519),
              ("Pesqueira", 55200, 55219), ("Serra Talhada", 56900, 56919), ("Petrolina", 56300, 56339), ("Belo Jardim", 55150, 55159)]
JORNADAS = [("07:00", "11:00", "12:00", "16:00"), ("08:00", "12:00", "13:00", "17:00"), ("06:00", "10:00", "11:00", "15:00")]
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def pis_valido(rng: random.Random) -> str:
    base = [rng.randint(0, 9) for _ in range(10)]
    base[0] = 1
    s = sum(d * p for d, p in zip(base, [3, 2, 9, 8, 7, 6, 5, 4, 3, 2]))
    dv = 11 - s % 11
    return "".join(map(str, base)) + str(0 if dv >= 10 else dv)


def so_digitos(s: str) -> str:
    return "".join(c for c in s if c.isdigit())


@dataclass
class Endereco:
    logradouro: str
    numero: str
    bairro: str
    municipio: str
    uf: str
    cep: str

    @property
    def linha(self) -> str:
        return f"{self.logradouro}, {self.numero}"

    @property
    def completo(self) -> str:
        return f"{self.logradouro}, {self.numero} – {self.bairro}, {self.municipio}/{self.uf}"


def gerar_endereco(rng: random.Random, fk: Faker, cidade: tuple | None = None) -> Endereco:
    nome, c0, c1 = cidade or rng.choice(CIDADES_PE)
    tipo = rng.choice(["Rua", "Rua", "Avenida", "Travessa", "Rua"])
    return Endereco(f"{tipo} {fk.last_name()} {fk.last_name()}", str(rng.randint(1, 1999)), fk.bairro(), nome, "PE",
                    f"{rng.randint(c0, c1)}{rng.randint(0, 999):03d}")


@dataclass
class Empresa:
    razao_social: str
    cnpj: str
    endereco: str
    cidade: str
    segmento: str
    end: Endereco | None = None


@dataclass
class Empregado:
    nome: str
    cpf: str
    pis: str
    matricula: str
    cargo: str
    cbo: str
    salario: float
    admissao: str
    jornada: tuple[str, str, str, str]
    empresa_cnpj: str
    desligado_em: str | None = None
    end: Endereco | None = None
    nascimento: str | None = None


@dataclass
class DiaTrabalho:
    data: str
    marcacoes: list[str]
    ocorrencia: str | None


@dataclass
class Universo:
    seed: int
    data_referencia: str
    empresas: list[Empresa]
    empregados: list[Empregado]
    competencias: list[str]
    meses: dict = field(default_factory=dict)  # (cpf, competencia) -> list[DiaTrabalho]

    def empregados_de(self, cnpj: str) -> list[Empregado]:
        return [e for e in self.empregados if e.empresa_cnpj == cnpj]

    def para_json(self) -> dict:
        d = asdict(self)
        d.pop("meses")
        return d


def _hm(minutos: int) -> str:
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def _min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def gerar_universo(seed: int, n_empresas=3, empregados_por_empresa=(6, 15), n_competencias=3, hoje: date | None = None) -> Universo:
    rng = random.Random(seed)
    fk = Faker("pt_BR")
    fk.seed_instance(seed)
    hoje = hoje or date.today()

    # competências: últimos n meses fechados
    comps = []
    a, m = hoje.year, hoje.month
    for _ in range(n_competencias):
        m -= 1
        if m == 0:
            a, m = a - 1, 12
        comps.append(f"{a:04d}-{m:02d}")
    comps.reverse()

    empresas, empregados = [], []
    for i in range(n_empresas):
        seg = rng.choice(list(SEGMENTOS))
        nome = f"{fk.last_name()} {seg.split()[0]} {rng.choice(['Serviços', 'Terceirização', 'Soluções'])} LTDA"
        cid = rng.choice(CIDADES_PE)
        end = gerar_endereco(rng, fk, cid)
        emp = Empresa(nome.upper(), so_digitos(fk.cnpj()), f"{end.linha} – {end.bairro}", f"{end.municipio}/{end.uf}", seg, end)
        empresas.append(emp)
        for j in range(rng.randint(*empregados_por_empresa)):
            cargo, s0, s1 = rng.choice(SEGMENTOS[seg])
            adm = hoje - timedelta(days=rng.randint(90, 2500))
            empregados.append(Empregado(
                nome=f"{fk.first_name()} {fk.last_name()} {fk.last_name()}".upper(),
                cpf=so_digitos(fk.cpf()), pis=pis_valido(rng), matricula=f"{rng.randint(100, 9999):06d}",
                cargo=cargo.upper(), cbo=f"{rng.randint(4000, 9999)}-{rng.randint(10, 99)}",
                salario=round(rng.uniform(s0, s1) / 10) * 10.0, admissao=adm.isoformat(),
                jornada=rng.choice(JORNADAS), empresa_cnpj=emp.cnpj,
                end=gerar_endereco(rng, fk, cid if rng.random() < 0.7 else None),
                nascimento=(adm - timedelta(days=rng.randint(18 * 365, 55 * 365))).isoformat(),
            ))
    # ~10% desligados na última competência (geram TRCT)
    ultimo = comps[-1]
    a, m = map(int, ultimo.split("-"))
    for e in empregados:
        if rng.random() < 0.12:
            e.desligado_em = date(a, m, rng.randint(10, calendar.monthrange(a, m)[1])).isoformat()

    u = Universo(seed, hoje.isoformat(), empresas, empregados, comps)
    for e in empregados:
        for c in comps:
            u.meses[(e.cpf, c)] = gerar_mes(rng, e, c)
    return u


def gerar_mes(rng: random.Random, e: Empregado, competencia: str, nc: str | None = None) -> list[DiaTrabalho]:
    """Mês de trabalho coerente com a jornada. nc: jornada_excessiva | intervalo_curto | ponto_britanico."""
    a, m = map(int, competencia.split("-"))
    ent, sai_int, ret, sai = map(_min, e.jornada)
    dias = []
    ultimo_dia = calendar.monthrange(a, m)[1]
    deslig = date.fromisoformat(e.desligado_em) if e.desligado_em else None
    uteis = [d for d in range(1, ultimo_dia + 1) if date(a, m, d).weekday() < 5]
    dia_nc = rng.choice(uteis) if nc in ("jornada_excessiva", "intervalo_curto") else None
    for d in range(1, ultimo_dia + 1):
        dt = date(a, m, d)
        if deslig and dt > deslig:
            dias.append(DiaTrabalho(dt.isoformat(), [], "DESLIGADO"))
            continue
        if dt.weekday() >= 5:
            dias.append(DiaTrabalho(dt.isoformat(), [], "FOLGA" if dt.weekday() == 5 else "DSR"))
            continue
        r = rng.random()
        if nc != "ponto_britanico" and r < 0.02:
            dias.append(DiaTrabalho(dt.isoformat(), [], "FALTA"))
            continue
        if nc != "ponto_britanico" and r < 0.04:
            dias.append(DiaTrabalho(dt.isoformat(), [], "ATESTADO"))
            continue
        if nc == "ponto_britanico":
            marc = [ent, sai_int, ret, sai]
        else:
            v = lambda lo, hi: rng.randint(lo, hi)  # noqa: E731
            e1 = ent + v(-12, 6)
            s1 = sai_int + v(-3, 6)
            r1 = max(s1 + 60, ret + v(-2, 8))  # intervalo nunca < 1h
            extra = rng.choice([0] * 6 + [v(20, 75)])
            s2 = sai + v(-3, 10) + extra
            marc = [e1, s1, r1, s2]
        if d == dia_nc and nc == "jornada_excessiva":
            marc[3] = marc[2] + 6 * 60 + rng.randint(30, 90)  # total > 10h
        if d == dia_nc and nc == "intervalo_curto":
            marc[2] = marc[1] + rng.randint(25, 40)
        dias.append(DiaTrabalho(dt.isoformat(), [_hm(x) for x in marc], None))
    return dias


def minutos_extras(dias: list[DiaTrabalho]) -> int:
    total = 0
    for d in dias:
        if len(d.marcacoes) == 4:
            m = [_min(x) for x in d.marcacoes]
            total += max(0, (m[1] - m[0]) + (m[3] - m[2]) - 480)
    return total


def faltas(dias: list[DiaTrabalho]) -> int:
    return sum(1 for d in dias if d.ocorrencia == "FALTA")


def nome_mes(competencia: str) -> str:
    a, m = competencia.split("-")
    return f"{MESES[int(m) - 1]}/{a}"
