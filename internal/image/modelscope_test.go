package image

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/geekjourneyx/md2wechat-skill/internal/config"
)

func TestNewModelScopeProvider(t *testing.T) {
	cfg := &config.Config{
		ImageAPIKey:  "test-key",
		ImageAPIBase: "https://api-inference.modelscope.cn/",
		ImageModel:   "Tongyi-MAI/Z-Image-Turbo",
	}

	p, err := NewModelScopeProvider(cfg)
	if err != nil {
		t.Fatalf("NewModelScopeProvider() error = %v", err)
	}

	if p.Name() != "ModelScope" {
		t.Errorf("Name() = %v, want ModelScope", p.Name())
	}

	if p.model != "Tongyi-MAI/Z-Image-Turbo" {
		t.Errorf("model = %v, want Tongyi-MAI/Z-Image-Turbo", p.model)
	}

	if p.apiKey != "test-key" {
		t.Errorf("apiKey = %v, want test-key", p.apiKey)
	}
}

func TestNewModelScopeProviderDefaults(t *testing.T) {
	cfg := &config.Config{
		ImageAPIKey: "test-key",
		// ImageAPIBase 和 ImageModel 为空，应使用默认值
	}

	p, err := NewModelScopeProvider(cfg)
	if err != nil {
		t.Fatalf("NewModelScopeProvider() error = %v", err)
	}

	if p.baseURL != "https://api-inference.modelscope.cn/" {
		t.Errorf("baseURL = %v, want https://api-inference.modelscope.cn/", p.baseURL)
	}

	if p.model != "Tongyi-MAI/Z-Image-Turbo" {
		t.Errorf("model = %v, want Tongyi-MAI/Z-Image-Turbo", p.model)
	}

	if p.pollInterval != 5*time.Second {
		t.Errorf("pollInterval = %v, want 5s", p.pollInterval)
	}

	if p.maxPollTime != 120*time.Second {
		t.Errorf("maxPollTime = %v, want 120s", p.maxPollTime)
	}
}

func TestModelScopeProvider_CreateTask(t *testing.T) {
	taskID := "test-task-123"
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// 验证请求
		if r.Method != "POST" {
			t.Errorf("Method = %v, want POST", r.Method)
		}
		if r.URL.Path != "/v1/images/generations" {
			t.Errorf("Path = %v, want /v1/images/generations", r.URL.Path)
		}
		if r.Header.Get("X-ModelScope-Async-Mode") != "true" {
			t.Errorf("X-ModelScope-Async-Mode header missing")
		}
		if r.Header.Get("Authorization") != "Bearer test-key" {
			t.Errorf("Authorization header incorrect")
		}

		// 返回 task_id
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{
			"task_id": taskID,
		})
	}))
	defer server.Close()

	cfg := &config.Config{
		ImageAPIKey:  "test-key",
		ImageAPIBase: server.URL,
		ImageModel:   "Tongyi-MAI/Z-Image-Turbo",
	}

	p, _ := NewModelScopeProvider(cfg)
	gotTaskID, err := p.createTask(context.Background(), "a golden cat")
	if err != nil {
		t.Fatalf("createTask() error = %v", err)
	}

	if gotTaskID != taskID {
		t.Errorf("taskID = %v, want %v", gotTaskID, taskID)
	}
}

func TestModelScopeProvider_PollTaskStatus(t *testing.T) {
	imageURL := "https://example.com/generated-image.png"
	pollCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			t.Errorf("Method = %v, want GET", r.Method)
		}
		if r.Header.Get("X-ModelScope-Task-Type") != "image_generation" {
			t.Errorf("X-ModelScope-Task-Type header missing")
		}

		pollCount++
		var response any
		if pollCount < 3 {
			// 前两次返回 PENDING/RUNNING
			status := "PENDING"
			if pollCount == 2 {
				status = "RUNNING"
			}
			response = map[string]any{
				"task_status": status,
			}
		} else {
			// 第三次返回成功
			response = map[string]any{
				"task_status":   "SUCCEED",
				"output_images": []string{imageURL},
			}
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	cfg := &config.Config{
		ImageAPIKey:  "test-key",
		ImageAPIBase: server.URL,
	}

	p, _ := NewModelScopeProvider(cfg)
	p.pollInterval = 10 * time.Millisecond // 加快测试速度

	gotURL, err := p.pollTaskStatus(context.Background(), "test-task-id")
	if err != nil {
		t.Fatalf("pollTaskStatus() error = %v", err)
	}

	if gotURL != imageURL {
		t.Errorf("URL = %v, want %v", gotURL, imageURL)
	}

	if pollCount != 3 {
		t.Errorf("poll count = %v, want 3", pollCount)
	}
}

func TestModelScopeProvider_Generate(t *testing.T) {
	imageURL := "https://example.com/generated-image.png"
	taskID := "test-task-456"
	var createCalled bool
	var statusCalled int

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "POST" && r.URL.Path == "/v1/images/generations" {
			createCalled = true
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]string{
				"task_id": taskID,
			})
		} else if r.Method == "GET" && r.URL.Path == "/v1/tasks/"+taskID {
			statusCalled++
			w.Header().Set("Content-Type", "application/json")
			// 第一次直接返回成功，简化测试
			json.NewEncoder(w).Encode(map[string]any{
				"task_status":   "SUCCEED",
				"output_images": []string{imageURL},
			})
		}
	}))
	defer server.Close()

	cfg := &config.Config{
		ImageAPIKey:  "test-key",
		ImageAPIBase: server.URL,
	}

	p, _ := NewModelScopeProvider(cfg)
	p.pollInterval = 10 * time.Millisecond

	result, err := p.Generate(context.Background(), "a golden cat")
	if err != nil {
		t.Fatalf("Generate() error = %v", err)
	}

	if !createCalled {
		t.Error("createTask was not called")
	}

	if statusCalled == 0 {
		t.Error("getTaskStatus was not called")
	}

	if result.URL != imageURL {
		t.Errorf("URL = %v, want %v", result.URL, imageURL)
	}

	if result.Model != "Tongyi-MAI/Z-Image-Turbo" {
		t.Errorf("Model = %v, want Tongyi-MAI/Z-Image-Turbo", result.Model)
	}
}

func TestModelScopeProvider_Generate_TaskFailed(t *testing.T) {
	taskID := "test-task-failed"

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "POST" && r.URL.Path == "/v1/images/generations" {
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]string{
				"task_id": taskID,
			})
		} else if r.Method == "GET" && r.URL.Path == "/v1/tasks/"+taskID {
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]any{
				"task_status": "FAILED",
			})
		}
	}))
	defer server.Close()

	cfg := &config.Config{
		ImageAPIKey:  "test-key",
		ImageAPIBase: server.URL,
	}

	p, _ := NewModelScopeProvider(cfg)
	p.pollInterval = 10 * time.Millisecond

	_, err := p.Generate(context.Background(), "test prompt")
	if err == nil {
		t.Fatal("Generate() should return error for failed task")
	}

	genErr, ok := err.(*GenerateError)
	if !ok {
		t.Fatalf("Error type = %T, want *GenerateError", err)
	}

	if genErr.Code != "task_failed" {
		t.Errorf("Error code = %v, want task_failed", genErr.Code)
	}
}

func TestModelScopeProvider_HandleErrorResponse_Unauthorized(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		w.Write([]byte(`{"message": "invalid token"}`))
	}))
	defer server.Close()

	cfg := &config.Config{
		ImageAPIKey:  "invalid-key",
		ImageAPIBase: server.URL,
	}

	p, _ := NewModelScopeProvider(cfg)
	_, err := p.Generate(context.Background(), "test")

	if err == nil {
		t.Fatal("Expected error for unauthorized request")
	}

	genErr, ok := err.(*GenerateError)
	if !ok {
		t.Fatalf("Error type = %T, want *GenerateError", err)
	}

	if genErr.Code != "unauthorized" {
		t.Errorf("Error code = %v, want unauthorized", genErr.Code)
	}

	if genErr.Provider != "ModelScope" {
		t.Errorf("Provider = %v, want ModelScope", genErr.Provider)
	}
}

func TestModelScopeProvider_HandleErrorResponse_RateLimit(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusTooManyRequests)
		w.Write([]byte(`{"message": "rate limit exceeded"}`))
	}))
	defer server.Close()

	cfg := &config.Config{
		ImageAPIKey:  "test-key",
		ImageAPIBase: server.URL,
	}

	p, _ := NewModelScopeProvider(cfg)
	_, err := p.Generate(context.Background(), "test")

	if err == nil {
		t.Fatal("Expected error for rate limit")
	}

	genErr, ok := err.(*GenerateError)
	if !ok {
		t.Fatalf("Error type = %T, want *GenerateError", err)
	}

	if genErr.Code != "rate_limit" {
		t.Errorf("Error code = %v, want rate_limit", genErr.Code)
	}
}

func TestGetModelScopeSupportedModels(t *testing.T) {
	models := GetModelScopeSupportedModels()
	if len(models) == 0 {
		t.Error("GetModelScopeSupportedModels() returned empty list")
	}

	found := false
	for _, m := range models {
		if m == "Tongyi-MAI/Z-Image-Turbo" {
			found = true
			break
		}
	}
	if !found {
		t.Error("Tongyi-MAI/Z-Image-Turbo not found in supported models")
	}
}
