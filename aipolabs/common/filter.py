from aipolabs.common.ai_service import AIService
from aipolabs.common.db.sql_models import Function
from aipolabs.common.logging import get_logger
from aipolabs.common.schemas.function import FilterResponse

logger = get_logger(__name__)


def filter_function_call(
    ai_service: AIService,
    function: Function,
    function_input: dict,
    custom_instructions: str,
) -> FilterResponse:
    args = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that looks at a function call and a custom instruction, then determines whether the function should be executed."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Decide if the function call should be allowed or not based on the rule, function definition, and input. "
                    f"Function name: {function.name}, "
                    f"Function description: {function.description}, "
                    f"Custom instruction: {custom_instructions},"
                    f"Function input: {function_input}"
                ),
            },
        ],
        "temperature": 0,
    }

    return ai_service.get_structured_response(response_format=FilterResponse, **args)
