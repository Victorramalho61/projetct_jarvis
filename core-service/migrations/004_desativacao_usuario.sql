-- core-service -- desativar usuário != solicitação pendente (2026-10-07).
-- Antes, active=false servia para os dois: o desativado caía no quadro "Solicitações pendentes"
-- e um clique em "Aprovar" devolvia o acesso (aconteceu com renata.facundo em 07/10).
--
-- deactivated_at/by : marca a desativação (pendente = active=false AND deactivated_at IS NULL)
-- token_version     : vai no JWT (claim "tv"); incrementar invalida todas as sessões do usuário.
--                     Os serviços revalidam a conta no banco a cada request (auth.py, cache 30s).
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS token_version integer NOT NULL DEFAULT 0;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS deactivated_at timestamptz;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS deactivated_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL;

-- Pedro e Renata, desativados por victor.ramalho em 07/10 (senha já invalidada na contenção)
UPDATE public.profiles p
SET deactivated_at = now(),
    deactivated_by = (SELECT id FROM public.profiles WHERE username = 'victor.ramalho'),
    token_version  = p.token_version + 1,
    password_hash  = NULL
WHERE p.username IN ('pedro.fernandes', 'renata.facundo') AND NOT p.active;
