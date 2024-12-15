import sqlite3


con = sqlite3.connect('instance/team_db_arch_2024.db')
cur = con.cursor()

# cur.execute('''DROP TABLE IF EXISTS supervisors''')
# cur.execute('''DROP TABLE IF EXISTS directions''')
# cur.execute('''DROP TABLE IF EXISTS contests''')
# cur.execute('''DROP TABLE IF EXISTS categories''')
# cur.execute('''DROP TABLE IF EXISTS cat_dir_contest''')
# cur.execute('''DROP TABLE IF EXISTS cats_supervisors''')

# cur.execute('''DROP TABLE IF EXISTS users''')
# cur.execute('''DROP TABLE IF EXISTS profile''')
# cur.execute('''DROP TABLE IF EXISTS team_application''')
# cur.execute('''DROP TABLE IF EXISTS cats_secretaries''')
#
cur.execute('''DROP TABLE IF EXISTS works''')
cur.execute('''DROP TABLE IF EXISTS work_cats''')
# cur.execute('''DROP TABLE IF EXISTS participation_statuses''')
cur.execute('''DROP TABLE IF EXISTS work_statuses''')
cur.execute('''DROP TABLE IF EXISTS applications_2_tour''')
cur.execute('''DROP TABLE IF EXISTS applied_for_online''')
cur.execute('''DROP TABLE IF EXISTS category_unions''')
cur.execute('''DROP TABLE IF EXISTS organisation_application''')
cur.execute('''DROP TABLE IF EXISTS participated_works''')
cur.execute('''DROP TABLE IF EXISTS work_organisations''')

# cur.execute('''DROP TABLE IF EXISTS report_dates''')

cur.execute('''DROP TABLE IF EXISTS participants_applied''')
cur.execute('''DROP TABLE IF EXISTS discounts''')
cur.execute('''DROP TABLE IF EXISTS bank_statement''')
cur.execute('''DROP TABLE IF EXISTS payment_registration''')


# cur.execute('''DROP TABLE IF EXISTS organising_committee''')


# cur.execute('''DROP TABLE IF EXISTS internal_reviewers''')
# cur.execute('''DROP TABLE IF EXISTS internal_reviews''')
# cur.execute('''DROP TABLE IF EXISTS work_reviews''')

# cur.execute('''DROP TABLE IF EXISTS internal_analysis''')
# cur.execute('''DROP TABLE IF EXISTS int_rev_comments''')
# cur.execute('''DROP TABLE IF EXISTS reviewer_comments''')

# cur.execute('''DROP TABLE IF EXISTS responsibilities''')
# cur.execute('''DROP TABLE IF EXISTS resp_assignment''')

cur.execute('''DROP TABLE IF EXISTS experts''')
cur.execute('''DROP TABLE IF EXISTS cat_experts''')


cur.execute('''DROP TABLE IF EXISTS yais_categories''')
cur.execute('''DROP TABLE IF EXISTS yais_works''')
cur.execute('''DROP TABLE IF EXISTS yais_authors''')
cur.execute('''DROP TABLE IF EXISTS yais_supervisors''')
cur.execute('''DROP TABLE IF EXISTS yais_classes''')
cur.execute('''DROP TABLE IF EXISTS yais_regions''')
cur.execute('''DROP TABLE IF EXISTS yais_cities''')
cur.execute('''DROP TABLE IF EXISTS yais_organisations''')
cur.execute('''DROP TABLE IF EXISTS yais_region_cities''')
cur.execute('''DROP TABLE IF EXISTS yais_region_cities''')
cur.execute('''DROP TABLE IF EXISTS yais_supervisor_organisation''')
cur.execute('''DROP TABLE IF EXISTS yais_work_organisation''')
cur.execute('''DROP TABLE IF EXISTS yais_work_author_supervisor''')
cur.execute('''DROP TABLE IF EXISTS yais_work_categories''')

cur.execute('''DROP TABLE IF EXISTS yais_work_payment''')
cur.execute('''DROP TABLE IF EXISTS yais_arrival''')
cur.execute('''DROP TABLE IF EXISTS yais_author_class''')
cur.execute('''DROP TABLE IF EXISTS yais_city_organisations''')


cur.execute('''DROP TABLE IF EXISTS mails''')
cur.execute('''DROP TABLE IF EXISTS work_mail''')

cur.execute('''DROP TABLE IF EXISTS tutor_user''')
cur.execute('''DROP TABLE IF EXISTS volunteer_tasks''')
# cur.execute('''DROP TABLE IF EXISTS school_classes''')
cur.execute('''DROP TABLE IF EXISTS student_class''')
cur.execute('''DROP TABLE IF EXISTS volunteer_assignment''')
cur.execute('''DROP TABLE IF EXISTS lesson_schedule''')
cur.execute('''DROP TABLE IF EXISTS lesson_group''')
cur.execute('''DROP TABLE IF EXISTS student_group''')
cur.execute('''DROP TABLE IF EXISTS lesson_group''')
