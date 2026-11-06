import { fireEvent, render, screen } from '@testing-library/react'
import { ComplianceRing, DataTable, EmptyState, Modal, StatusPill } from '.'
import { filterNav } from '../shell/nav'
import { Home } from 'lucide-react'

describe('componentes', () => {
  it('StatusPill usa os rótulos e cores de status', () => {
    render(<StatusPill status="A_VENCER" />)
    expect(screen.getByText('A vencer').className).toContain('text-warning')
  })
  it('ComplianceRing expõe o percentual para leitores de tela', () => {
    render(<ComplianceRing pct={87} />)
    expect(screen.getByRole('img', { name: 'Conformidade 87%' })).toBeInTheDocument()
  })
  it('Modal fecha com Esc e tem papel de diálogo', () => {
    const onClose = vi.fn()
    render(<Modal open onClose={onClose} title="Teste"><p>conteúdo</p></Modal>)
    expect(screen.getByRole('dialog')).toHaveAccessibleName('Teste')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })
  it('DataTable mostra estado vazio', () => {
    render(<DataTable rows={[]} cols={[]} empty={<EmptyState title="Nada aqui" />} />)
    expect(screen.getByText('Nada aqui')).toBeInTheDocument()
  })
})

describe('navegação por perfil', () => {
  const user: any = { role: 'RH', perms: ['lotes:enviar'] }
  const link = (to: string, roles?: any, perm?: string) => ({ kind: 'link' as const, to, label: to, icon: Home, roles, perm })
  it('filtra por perfil e permissão; grupo com 1 filho vira link; grupo vazio some', () => {
    const out = filterNav([link('/a', ['MASTER']), link('/b', ['RH']), link('/c', undefined, 'saude:ler'),
      { kind: 'group', label: 'G1', icon: Home, children: [link('/d', ['RH']), link('/e', ['MASTER'])] },
      { kind: 'group', label: 'G2', icon: Home, children: [link('/f', ['MASTER'])] }], user)
    expect(out.map((e: any) => e.to ?? e.label)).toEqual(['/b', '/d'])
  })
})
