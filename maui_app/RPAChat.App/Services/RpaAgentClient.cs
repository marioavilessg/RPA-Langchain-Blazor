using System.Net.Http.Json;
using System.Text.Json.Serialization;

namespace RPAChat.App.Services;

public class ChatRequest
{
    [JsonPropertyName("message")]
    public string Message { get; set; } = "";

    [JsonPropertyName("session_id")]
    public string SessionId { get; set; } = "";
}

public class ChatResponse
{
    [JsonPropertyName("ok")]
    public bool Ok { get; set; }

    [JsonPropertyName("session_id")]
    public string SessionId { get; set; } = "";

    [JsonPropertyName("response")]
    public string Response { get; set; } = "";

    [JsonPropertyName("error")]
    public string? Error { get; set; }
}

public class RpaAgentClient
{
    private readonly HttpClient _httpClient;

    public RpaAgentClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<ChatResponse> SendAsync(string message, string sessionId)
    {
        var request = new ChatRequest
        {
            Message = message,
            SessionId = sessionId
        };

        var response = await _httpClient.PostAsJsonAsync("chat", request);

        if (!response.IsSuccessStatusCode)
        {
            var errorBody = await response.Content.ReadAsStringAsync();

            return new ChatResponse
            {
                Ok = false,
                SessionId = sessionId,
                Response = "",
                Error = $"API HTTP {(int)response.StatusCode}: {errorBody}"
            };
        }

        var result = await response.Content.ReadFromJsonAsync<ChatResponse>();

        if (result == null)
        {
            return new ChatResponse
            {
                Ok = false,
                SessionId = sessionId,
                Response = "",
                Error = "La API devolvio una respuesta vacia."
            };
        }

        return result;
    }
}
