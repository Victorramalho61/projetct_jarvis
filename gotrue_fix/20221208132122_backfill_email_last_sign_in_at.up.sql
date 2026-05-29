do 
  $$
begin
update auth.identities
  set last_sign_in_at = '2022-11-25'
  where
    last_sign_in_at is null and
    created_at = 
  '2022-11-25' and
    updated_at = '2022-11-25' and
    provider = 'email' and
    id::text = user_id::text;
end $$;