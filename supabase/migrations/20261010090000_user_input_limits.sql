-- Server-side limits for sign-up data, so they hold even if someone bypasses the web form.
create or replace function public.verity_validate_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  full_name text := coalesce(new.raw_user_meta_data ->> 'full_name', '');
begin
  if length(coalesce(new.email, '')) > 254 then
    raise exception 'Email address is too long (max 254 characters).';
  end if;
  if length(full_name) > 50 then
    raise exception 'Name is too long (max 50 characters).';
  end if;
  if full_name ~ '[0-9<>{}\[\]@#$%^&*=+\\/|~`_;:!?"]' then
    raise exception 'Name can only contain letters, spaces, apostrophes, dots and hyphens.';
  end if;
  return new;
end;
$$;

revoke all on function public.verity_validate_user() from public, anon, authenticated;

drop trigger if exists verity_validate_user on auth.users;
create trigger verity_validate_user
  before insert or update of email, raw_user_meta_data on auth.users
  for each row execute function public.verity_validate_user();
