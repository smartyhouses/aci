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
    help="project id under which the linked account will be created",
)
@click.option("--app-name", "app_name", required=True, help="name of the app to link account for")
@click.option(
    "--linked-account-owner-id",
    "linked_account_owner_id",
    required=True,
    help="owner id for the linked account",
)
@click.option(
    "--verbose", is_flag=True, help="provide this flag to print output as it is processed"
)
@click.option(
    "--skip-dry-run",
    is_flag=True,
    help="provide this flag to run the command and apply changes to the database",
)
def create_linked_account_with_default_credentials(
    project_id: UUID,
    app_name: str,
    linked_account_owner_id: str,
    verbose: bool,
    skip_dry_run: bool,
) -> None:
    """
    Create a linked account using Aipolabs default credentials.
    """
    create_linked_account_with_default_credentials_helper(
        project_id, app_name, linked_account_owner_id, verbose, skip_dry_run
    )


def create_linked_account_with_default_credentials_helper(
    project_id: UUID,
    app_name: str,
    linked_account_owner_id: str,
    verbose: bool,
    skip_dry_run: bool,
) -> None:
    """Helper function to create a linked account with default credentials"""
    with utils.create_db_session(config.DB_FULL_URL) as db_session:
        # Check if app configuration exists
        app_configuration = crud.app_configurations.get_app_configuration(
            db_session, project_id, app_name
        )
        if not app_configuration:
            click.echo(f"Error: Configuration not found for app {app_name}")
            return

        # Check if app has default credentials
        app_default_credentials = app_configuration.app.default_security_credentials_by_scheme.get(
            app_configuration.security_scheme
        )
        if not app_default_credentials:
            click.echo(
                f"Error: No default credentials provided by Aipolabs for app {app_name} "
                f"with security scheme {app_configuration.security_scheme}"
            )
            return

        # Check if linked account already exists
        linked_account = crud.linked_accounts.get_linked_account(
            db_session,
            project_id,
            app_name,
            linked_account_owner_id,
        )

        if linked_account:
            # Update existing account
            linked_account = crud.linked_accounts.update_linked_account(
                db_session, linked_account, app_configuration.security_scheme, {}
            )
            action = "Updated"
        else:
            # Create new account
            linked_account = crud.linked_accounts.create_linked_account(
                db_session,
                project_id,
                app_name,
                linked_account_owner_id,
                app_configuration.security_scheme,
                enabled=True,
            )
            action = "Created"

        if not skip_dry_run:
            if verbose:
                click.echo(create_headline(f"Will {action.lower()} linked account for {app_name}"))
                click.echo(linked_account)
            click.echo(create_headline("Provide --skip-dry-run to commit changes"))
            db_session.rollback()
        else:
            if verbose:
                click.echo(create_headline(f"{action} linked account for {app_name}"))
                click.echo(linked_account)
            db_session.commit()
