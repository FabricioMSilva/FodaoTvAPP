-- Atomic catalogue replacement for administrators.
-- The browser sends a parsed M3U payload; this function replaces all streams
-- only after verifying that the current authenticated profile is an admin.

create or replace function public.replace_catalog(catalog jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  imported_groups integer := 0;
  imported_streams integer := 0;
begin
  if not public.is_admin() then
    raise exception 'Only administrators can replace the catalogue';
  end if;

  if jsonb_typeof(catalog) <> 'object'
    or jsonb_typeof(catalog -> 'groups') <> 'array'
    or jsonb_typeof(catalog -> 'streams') <> 'array' then
    raise exception 'Invalid catalogue payload';
  end if;

  -- The function runs in one transaction. A malformed request rolls back and
  -- preserves the previous catalogue.
  delete from public.streams;
  delete from public.content_groups;

  insert into public.content_groups (category_id, name, sort_order)
  select categories.id, source.name, source.sort_order
  from (
    select distinct on (category_slug, name)
      category_slug, name, coalesce(sort_order, 0) as sort_order
    from jsonb_to_recordset(catalog -> 'groups')
      as group_rows(category_slug text, name text, sort_order integer)
    where nullif(trim(name), '') is not null
    order by category_slug, name, sort_order
  ) source
  join public.categories on categories.slug = source.category_slug;

  get diagnostics imported_groups = row_count;

  insert into public.streams (
    category_id, group_id, name, stream_url, logo_url, stream_type, is_active, metadata
  )
  select categories.id, content_groups.id, source.name, source.stream_url,
    nullif(source.logo_url, ''), source.stream_type, true, coalesce(source.metadata, '{}'::jsonb)
  from (
    select distinct on (category_slug, group_name, name)
      category_slug, group_name, name, stream_url, logo_url, stream_type, metadata
    from jsonb_to_recordset(catalog -> 'streams') as stream_rows(
      category_slug text,
      group_name text,
      name text,
      stream_url text,
      logo_url text,
      stream_type text,
      metadata jsonb
    )
    where nullif(trim(name), '') is not null and nullif(trim(stream_url), '') is not null
    order by category_slug, group_name, name
  ) source
  join public.categories on categories.slug = source.category_slug
  join public.content_groups on content_groups.category_id = categories.id
    and content_groups.name = source.group_name;

  get diagnostics imported_streams = row_count;
  return jsonb_build_object('groups', imported_groups, 'streams', imported_streams);
end;
$$;

revoke all on function public.replace_catalog(jsonb) from public;
grant execute on function public.replace_catalog(jsonb) to authenticated;
