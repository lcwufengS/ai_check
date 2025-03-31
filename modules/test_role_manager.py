import pytest
from unittest.mock import Mock, patch
from .role_manager import AIModel
from openai import OpenAI

@pytest.fixture
def ai_model():
    """创建AIModel实例的fixture"""
    return AIModel(
        api_base="https://api.example.com",
        model_name="test-model",
        api_key="test-key",
        role_name="test-role"
    )

def test_init(ai_model):
    """测试AIModel初始化"""
    assert ai_model.api_base == "https://api.example.com"
    assert ai_model.model_name == "test-model"
    assert ai_model.api_key == "test-key"
    assert ai_model.role_name == "test-role"
    assert isinstance(ai_model.client, OpenAI)

@patch('openai.OpenAI')
def test_chat_completion_success(mock_openai):
    """测试正常的chat completion调用"""
    # 设置mock响应
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "测试响应"
    
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai.return_value = mock_client
    
    model = AIModel(
        api_base="https://api.example.com",
        model_name="test-model",
        api_key="test-key",
        role_name="test-role"
    )
    
    messages = [{"role": "user", "content": "测试消息"}]
    response = model.chat_completion(messages)
    
    assert response is not None
    assert response["choices"][0]["message"]["content"] == "测试响应"
    mock_client.chat.completions.create.assert_called_once_with(
        model="test-model",
        messages=messages,
        temperature=0.7
    )

@patch('openai.OpenAI')
def test_chat_completion_stream(mock_openai):
    """测试流式响应模式"""
    mock_stream = Mock()
    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_stream
    mock_openai.return_value = mock_client
    
    model = AIModel(
        api_base="https://api.example.com",
        model_name="test-model",
        api_key="test-key",
        role_name="test-role"
    )
    
    messages = [{"role": "user", "content": "测试消息"}]
    response = model.chat_completion(messages, stream=True)
    
    assert response == mock_stream
    mock_client.chat.completions.create.assert_called_once_with(
        model="test-model",
        messages=messages,
        temperature=0.7,
        stream=True
    )

@patch('openai.OpenAI')
def test_chat_completion_error(mock_openai):
    """测试错误处理"""
    mock_client = Mock()
    mock_client.chat.completions.create.side_effect = Exception("API错误")
    mock_openai.return_value = mock_client
    
    model = AIModel(
        api_base="https://api.example.com",
        model_name="test-model",
        api_key="test-key",
        role_name="test-role"
    )
    
    messages = [{"role": "user", "content": "测试消息"}]
    response = model.chat_completion(messages)
    
    assert response is None