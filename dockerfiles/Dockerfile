FROM odoo:17

# Ensure dependencies can be installed
USER root  

# Ensure dbfilter is correctly configured
RUN echo "dbfilter = .*" >> /etc/odoo/odoo.conf

# Switch back to Odoo user for security
USER odoo  

#-------------------- New Configuration to fix error-------------------
# FROM odoo:17

# # Ensure dependencies can be installed
# USER root  

# # Configure Odoo for production database handling and fix transaction errors
# RUN echo "dbfilter = .*" >> /etc/odoo/odoo.conf && \
#     echo "db_maxconn = 64" >> /etc/odoo/odoo.conf && \
#     echo "max_cron_threads = 2" >> /etc/odoo/odoo.conf && \
#     echo "workers = 4" >> /etc/odoo/odoo.conf && \
#     echo "limit_memory_hard = 2684354560" >> /etc/odoo/odoo.conf && \
#     echo "limit_memory_soft = 2147483648" >> /etc/odoo/odoo.conf && \
#     echo "limit_request = 8192" >> /etc/odoo/odoo.conf && \
#     echo "limit_time_cpu = 600" >> /etc/odoo/odoo.conf && \
#     echo "limit_time_real = 1200" >> /etc/odoo/odoo.conf && \
#     echo "log_level = info" >> /etc/odoo/odoo.conf && \
#     echo "logfile = /var/log/odoo/odoo.log" >> /etc/odoo/odoo.conf

# # Create log directory
# RUN mkdir -p /var/log/odoo && chown odoo:odoo /var/log/odoo

# # Switch back to Odoo user for security
# USER odoo