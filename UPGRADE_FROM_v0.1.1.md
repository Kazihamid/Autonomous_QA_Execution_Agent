# Upgrade from v0.1.1

The safest path for an existing local v0.1.1 installation is to apply the provided **Vertical Slice 2 Upgrade Pack** over the existing project folder. This preserves the current Docker Compose project/volume and allows Flyway V003 to upgrade the existing database without deleting Workspace/Application/Environment data.

Do **not** run `RESET_PROJECT.bat` during the upgrade unless you intentionally want to delete local data.
