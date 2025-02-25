import json
from uuid import UUID

import click

from aipolabs.cli import config
from aipolabs.common import utils
from aipolabs.common.db import crud
from aipolabs.common.enums import SecurityScheme
from aipolabs.common.logging import create_headline
from aipolabs.common.schemas.app_configurations import AppConfigurationCreate


@click.command()
@click.option(
    "--project-id",
    "project_id",
    required=True,
    type=UUID,
    help="project id under which the app is configured",
)
@click.option("--app-name", "app_name", required=True, help="name of the app to configure")
@click.option(
    "--security-scheme",
    "security_scheme",
    required=True,
    type=click.Choice([scheme.value for scheme in SecurityScheme]),
    help="security scheme to use for app configuration",
)
@click.option(
    "--security-scheme-overrides",
    "security_scheme_overrides",
    required=False,
    default="{}",
    type=str,
    help="JSON string containing security scheme overrides",
)
@click.option(
    "--all-functions-enabled",
    "all_functions_enabled",
    required=False,
    default=False,
    type=bool,
    help="whether all functions are enabled",
)
@click.option(
    "--enabled-functions",
    "enabled_functions",
    required=False,
    default=[],
    type=list[str],
    help="list of function names to enable for the app",
)
@click.option(
    "--verbose", is_flag=True, help="provide this flag to print output as it is processed"
)
@click.option(
    "--skip-dry-run",
    is_flag=True,
    help="provide this flag to run the command and apply changes to the database",
)
def create_app_configuration(
    project_id: UUID,
    app_name: str,
    security_scheme: str,
    security_scheme_overrides: str,
    all_functions_enabled: bool,
    enabled_functions: list[str],
    verbose: bool,
    skip_dry_run: bool,
) -> None:
    """
    Create an app configuration for a project.
    """
    create_app_configuration_helper(
        project_id,
        app_name,
        security_scheme,
        security_scheme_overrides,
        all_functions_enabled,
        enabled_functions,
        verbose,
        skip_dry_run,
    )


def create_app_configuration_helper(
    project_id: UUID,
    app_name: str,
    security_scheme: str,
    security_scheme_overrides: str,
    all_functions_enabled: bool,
    enabled_functions: list[str],
    verbose: bool,
    skip_dry_run: bool,
) -> None:
    """Helper function to create an app configuration"""
    # Create configuration object
    with utils.create_db_session(config.DB_FULL_URL) as db_session:
        app = crud.apps.get_app(db_session, app_name, public_only=False, active_only=True)
        if not app:
            click.echo(f"Error: App {app_name} not found")
            return

        # Check if configuration already exists
        if crud.app_configurations.app_configuration_exists(db_session, project_id, app_name):
            click.echo(f"Error: Configuration already exists for app {app_name}")
            return

        app_config = AppConfigurationCreate(
            app_name=app_name,
            security_scheme=SecurityScheme(security_scheme),
            security_scheme_overrides=json.loads(security_scheme_overrides),
            all_functions_enabled=all_functions_enabled,
            enabled_functions=enabled_functions,
        )

        # Create configuration
        app_configuration = crud.app_configurations.create_app_configuration(
            db_session, project_id, app_config
        )

        if not skip_dry_run:
            if verbose:
                click.echo(create_headline(f"Will configure app {app_name}"))
                click.echo(app_configuration)
            click.echo(create_headline("Provide --skip-dry-run to commit changes"))
            db_session.rollback()
        else:
            if verbose:
                click.echo(create_headline(f"Created configuration for app {app_name}"))
                click.echo(app_configuration)
            db_session.commit()
