import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { vi } from 'vitest'
import { EntityFinder } from './EntityFinder'
import { empresaPath } from '@/features/rh/Fornecedores'

const RESULTADO = {
  funcionarios: [{ id: 'f1', nome: 'CARLOS EDUARDO SILVA', cpf_mascarado: '***.712.903-**', status: 'ATIVO', setor: 'Manutenção', vinculo: 'PROPRIA', empresa: null }],
  setores: [{ id: 's1', nome: 'Manutenção', funcionarios: 3 }],
  empresas: [
    { id: 't1', cnpj: '44555666000181', nome: 'SEGURA VIGILÂNCIA LTDA', tipo: 'TERCEIRIZADA', status: 'ATIVO', funcionarios: 2 },
    { id: 'p1', cnpj: '11222333000181', nome: 'BRILHO LIMPEZA LTDA', tipo: 'FORNECEDOR', status: 'ATIVO', funcionarios: 0 },
  ],
}

function Local() { return <p data-testid="rota">{useLocation().pathname}</p> }
function montar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}><MemoryRouter><EntityFinder /><Routes><Route path="*" element={<Local />} /></Routes></MemoryRouter></QueryClientProvider>)
}

describe('localizador do topo', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async (url: URL | string) => new Response(JSON.stringify(String(url).includes('/directory/search') ? RESULTADO : {}), { status: 200, headers: { 'Content-Type': 'application/json' } })))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('agrupa pessoa, setor, terceirizada e fornecedor, e abre a ficha certa com o teclado', async () => {
    montar()
    const campo = screen.getByRole('combobox')
    fireEvent.change(campo, { target: { value: 'sil' } })
    await screen.findByText('CARLOS EDUARDO SILVA')
    for (const g of ['Funcionários', 'Setores', 'Terceirizadas', 'Fornecedores']) expect(screen.getByRole('group', { name: g })).toBeTruthy()
    expect(screen.getByText(/\*\*\*\.712\.903-\*\*/)).toBeTruthy()  // só o CPF mascarado aparece
    fireEvent.keyDown(campo, { key: 'ArrowDown' }); fireEvent.keyDown(campo, { key: 'ArrowDown' }); fireEvent.keyDown(campo, { key: 'ArrowDown' })
    fireEvent.keyDown(campo, { key: 'Enter' })  // 4º resultado: o fornecedor
    await waitFor(() => expect(screen.getByTestId('rota').textContent).toBe('/app/fornecedores/p1'))
  })

  it('com menos de 2 letras não consulta a API', async () => {
    montar()
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'a' } })
    await new Promise((r) => setTimeout(r, 350))
    expect((globalThis.fetch as any).mock.calls.filter((c: any[]) => String(c[0]).includes('/directory/search'))).toHaveLength(0)
  })
})

describe('endereço da empresa', () => {
  it('terceirizada e fornecedor têm lista e ficha próprias', () => {
    expect(empresaPath('TERCEIRIZADA')).toBe('/app/terceirizadas')
    expect(empresaPath('FORNECEDOR', 'x1')).toBe('/app/fornecedores/x1')
    expect(empresaPath(undefined, 'x2')).toBe('/app/fornecedores/x2')
  })
})
