BEGIN;

UPDATE app_logs SET message = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(message,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE message LIKE '%├%';

UPDATE fiscal_companies SET nome = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(nome,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE nome LIKE '%├%';

UPDATE fiscal_companies SET cidade = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(cidade,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE cidade LIKE '%├%';

UPDATE fiscal_documents SET destinatario_nome = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(destinatario_nome,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE destinatario_nome LIKE '%├%';

UPDATE fiscal_documents SET emitente_nome = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(emitente_nome,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE emitente_nome LIKE '%├%';

UPDATE fiscal_documents SET municipio_nome = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(municipio_nome,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE municipio_nome LIKE '%├%';

UPDATE fiscal_documents SET xml_content = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(xml_content,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE xml_content LIKE '%├%';

UPDATE fiscal_nfse_municipalities SET municipio_nome = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(municipio_nome,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE municipio_nome LIKE '%├%';

UPDATE freshservice_groups SET name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE name LIKE '%├%';

UPDATE freshservice_tickets SET subject = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(subject,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE subject LIKE '%├%';

UPDATE monitored_systems SET name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE name LIKE '%├%';

UPDATE monitored_systems SET description = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(description,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE description LIKE '%├%';

UPDATE payfly_media_posts SET full_text = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(full_text,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE full_text LIKE '%├%';

UPDATE payfly_media_posts SET snippet = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(snippet,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE snippet LIKE '%├%';

UPDATE payfly_media_posts SET source = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(source,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE source LIKE '%├%';

UPDATE payfly_media_posts SET title = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(title,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE title LIKE '%├%';

UPDATE payfly_reservations SET approver_name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(approver_name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE approver_name LIKE '%├%';

UPDATE payfly_reservations SET cancellation_policy = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(cancellation_policy,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE cancellation_policy LIKE '%├%';

UPDATE payfly_reservations SET company_name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(company_name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE company_name LIKE '%├%';

UPDATE payfly_reservations SET cost_center_name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(cost_center_name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE cost_center_name LIKE '%├%';

UPDATE payfly_reservations SET hotel_address = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(hotel_address,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE hotel_address LIKE '%├%';

UPDATE payfly_reservations SET hotel_city = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(hotel_city,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE hotel_city LIKE '%├%';

UPDATE payfly_reservations SET hotel_name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(hotel_name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE hotel_name LIKE '%├%';

UPDATE payfly_reservations SET passenger_department_name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(passenger_department_name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE passenger_department_name LIKE '%├%';

UPDATE payfly_reservations SET passenger_name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(passenger_name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE passenger_name LIKE '%├%';

UPDATE payfly_reservations SET project_name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(project_name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE project_name LIKE '%├%';

UPDATE payfly_reservations SET reason_name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(reason_name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE reason_name LIKE '%├%';

UPDATE payfly_reservations SET room_name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(room_name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE room_name LIKE '%├%';

UPDATE payfly_reservations SET solicitor_name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(solicitor_name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE solicitor_name LIKE '%├%';

UPDATE payfly_reservations SET status = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(status,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE status LIKE '%├%';

UPDATE payfly_reservations SET travel_justification_name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(travel_justification_name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE travel_justification_name LIKE '%├%';

UPDATE performance_branches SET name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE name LIKE '%├%';

UPDATE performance_companies SET name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE name LIKE '%├%';

UPDATE performance_employees SET name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE name LIKE '%├%';

UPDATE performance_employees SET cargo = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(cargo,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE cargo LIKE '%├%';

UPDATE performance_indicators SET name = REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(name,'├º','ç'),'├╡','õ'),'├¡','í'),'├ú','ã'),'├í','á'),'├¬','ê'),'├┤','ô'),'├║','ú'),'├ü','Á'),'├ç','Ç'),'├â','Ã'),'├ë','É') WHERE name LIKE '%├%';

COMMIT;
