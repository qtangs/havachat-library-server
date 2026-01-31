"""Test token tracking and usage summary in LLMClient."""

from havachat.utils.llm_client import LLMClient, TokenUsage


def test_token_tracking():
    """Test token usage tracking and cost calculation."""
    # Use dummy API key for testing (won't make actual API calls)
    # Explicitly set model to avoid env var override
    client = LLMClient(api_key="sk-test-dummy-key-for-testing", model="gpt-4o-mini")
    
    # Simulate some usage
    client.total_usage.prompt_tokens = 1000
    client.total_usage.completion_tokens = 500
    client.total_usage.total_tokens = 1500
    client.total_usage.cached_tokens = 300
    
    # Get usage summary
    summary = client.get_usage_summary()
    
    print("=" * 80)
    print("TOKEN USAGE SUMMARY")
    print("=" * 80)
    print(f"Model: {summary['model']}")
    print(f"Prompt tokens: {summary['prompt_tokens']:,}")
    print(f"Completion tokens: {summary['completion_tokens']:,}")
    print(f"Total tokens: {summary['total_tokens']:,}")
    print(f"Cached tokens: {summary['cached_tokens']:,}")
    print(f"Cache hit rate: {summary['cache_hit_rate']}")
    print(f"Estimated cost: ${summary['estimated_cost_usd']:.4f}")
    print(f"  - Input cost: ${summary['input_cost_usd']:.4f}")
    print(f"  - Output cost: ${summary['output_cost_usd']:.4f}")
    print("=" * 80)
    
    # Verify calculations
    assert summary['model'] == 'gpt-4o-mini'
    assert summary['prompt_tokens'] == 1000
    assert summary['cached_tokens'] == 300
    assert summary['cache_hit_rate'] == '30.0%'
    
    # Cost calculation:
    # Uncached prompt: 1000 - 300 = 700 tokens
    # Input cost: (700 * 0.15 + 300 * 0.075) / 1M = 0.0001275
    # Output cost: 500 * 0.60 / 1M = 0.0003
    # Total: ~0.0004275
    expected_cost = round((700 * 0.15 + 300 * 0.075) / 1_000_000 + (500 * 0.60) / 1_000_000, 4)
    assert summary['estimated_cost_usd'] == expected_cost
    
    print(f"\n✓ All assertions passed!")
    print(f"✓ Expected cost: ${expected_cost:.4f} matches calculated cost")
    
    # Test reset
    client.reset_usage()
    assert client.total_usage.prompt_tokens == 0
    assert client.total_usage.total_tokens == 0
    print(f"✓ Reset usage works correctly")
    
    print("\n" + "=" * 80)
    print("All token tracking tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    test_token_tracking()
