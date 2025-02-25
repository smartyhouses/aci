from uuid import UUID

import click

from aipolabs.cli import config
from aipolabs.common import utils
from aipolabs.common.db import crud
from aipolabs.common.logging import create_headline


@click.command()
@click.option(
    "--project-id",
    "project_id",
    required=True,
    type=UUID,
    help="project id under which the app is configured",
)
@click.option(
    "--app-name", "app_name", required=True, help="name of the app configuration to delete"
)
@click.option(
    "--verbose", is_flag=True, help="provide this flag to print output as it is processed"
)
@click.option(
    "--skip-dry-run",
    is_flag=True,
    help="provide this flag to run the command and apply changes to the database",
)
def delete_app_configuration(
    project_id: UUID,
    app_name: str,
    verbose: bool,
    skip_dry_run: bool,
) -> None:
    """
    Delete an app configuration for a project.
    Warning: This will delete the app configuration from the project,
    associated linked accounts, and then the app configuration record itself.
    """
    delete_app_configuration_helper(project_id, app_name, verbose, skip_dry_run)


def delete_app_configuration_helper(
    project_id: UUID,
    app_name: str,
    verbose: bool,
    skip_dry_run: bool,
) -> None:
    """Helper function to delete an app configuration"""
    with utils.create_db_session(config.DB_FULL_URL) as db_session:
        # Check if configuration exists
        app_configuration = crud.app_configurations.get_app_configuration(
            db_session, project_id, app_name
        )
        if not app_configuration:
            click.echo(f"Error: Configuration not found for app {app_name}")
            return

        # Delete linked accounts
        number_of_linked_accounts = crud.linked_accounts.delete_linked_accounts(
            db_session, project_id, app_name
        )

        # Delete app configuration
        crud.app_configurations.delete_app_configuration(db_session, project_id, app_name)

        if not skip_dry_run:
            if verbose:
                click.echo(create_headline(f"Will delete configuration for app {app_name}"))
                click.echo(f"This will delete {number_of_linked_accounts} linked account(s)")
            click.echo(create_headline("Provide --skip-dry-run to commit changes"))
            db_session.rollback()
        else:
            if verbose:
                click.echo(create_headline(f"Deleted configuration for app {app_name}"))
                click.echo(f"Deleted {number_of_linked_accounts} linked account(s)")
            db_session.commit()
