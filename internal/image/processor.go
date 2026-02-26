package image

import (
	"context"
	"fmt"
	"os"

	"github.com/geekjourneyx/md2wechat-skill/internal/config"
	"github.com/geekjourneyx/md2wechat-skill/internal/wechat"
	"go.uber.org/zap"
)

// Processor 图片处理器
type Processor struct {
	cfg        *config.Config
	log        *zap.Logger
	ws         *wechat.Service
	compressor *Compressor
	provider   Provider
}

// NewProcessor 创建图片处理器
func NewProcessor(cfg *config.Config, log *zap.Logger) *Processor {
	// 创建图片生成 Provider
	provider, err := NewProvider(cfg)
	if err != nil {
		// 如果配置了 API Key 但创建失败，记录警告
		if cfg.ImageAPIKey != "" {
			log.Warn("failed to create image provider, AI image generation will be unavailable", zap.Error(err))
		}
	}

	return &Processor{
		cfg:        cfg,
		log:        log,
		ws:         wechat.NewService(cfg, log),
		compressor: NewCompressor(log, cfg.MaxImageWidth, cfg.MaxImageSize),
		provider:   provider,
	}
}

// UploadResult 上传结果
type UploadResult struct {
	MediaID   string `json:"media_id"`
	WechatURL string `json:"wechat_url"`
	Width     int    `json:"width"`
	Height    int    `json:"height"`
}

// UploadLocalImage 上传本地图片
func (p *Processor) UploadLocalImage(filePath string) (*UploadResult, error) {
	p.log.Info("uploading local image", zap.String("path", filePath))

	// 检查文件是否存在
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		return nil, fmt.Errorf("file not found: %s", filePath)
	}

	// 检查图片格式
	if !IsValidImageFormat(filePath) {
		return nil, fmt.Errorf("unsupported image format: %s", filePath)
	}

	// 如果需要压缩，先处理
	processedPath := filePath
	if p.cfg.CompressImages {
		compressedPath, compressed, err := p.compressor.CompressImage(filePath)
		if err != nil {
			p.log.Warn("compress failed, using original", zap.Error(err))
		} else if compressed {
			processedPath = compressedPath
			defer os.Remove(compressedPath)
			p.log.Info("using compressed image", zap.String("path", processedPath))
		}
	}

	// 上传到微信
	result, err := p.ws.UploadMaterialWithRetry(processedPath, 3)
	if err != nil {
		return nil, err
	}

	return &UploadResult{
		MediaID:   result.MediaID,
		WechatURL: result.WechatURL,
	}, nil
}

// DownloadAndUpload 下载在线图片并上传
func (p *Processor) DownloadAndUpload(url string) (*UploadResult, error) {
	p.log.Info("downloading and uploading image", zap.String("url", url))

	// 下载图片
	tmpPath, err := wechat.DownloadFile(url)
	if err != nil {
		return nil, fmt.Errorf("download failed: %w", err)
	}
	defer os.Remove(tmpPath)

	// 检查格式
	if !IsValidImageFormat(tmpPath) {
		return nil, fmt.Errorf("downloaded file is not a valid image")
	}

	// 压缩（如果需要）
	processedPath := tmpPath
	if p.cfg.CompressImages {
		compressedPath, compressed, err := p.compressor.CompressImage(tmpPath)
		if err != nil {
			p.log.Warn("compress failed, using original", zap.Error(err))
		} else if compressed {
			processedPath = compressedPath
			defer os.Remove(compressedPath)
			p.log.Info("using compressed image", zap.String("path", processedPath))
		}
	}

	// 上传到微信
	result, err := p.ws.UploadMaterialWithRetry(processedPath, 3)
	if err != nil {
		return nil, err
	}

	return &UploadResult{
		MediaID:   result.MediaID,
		WechatURL: result.WechatURL,
	}, nil
}

// GenerateAndUploadResult AI 生成图片结果
type GenerateAndUploadResult struct {
	Prompt      string `json:"prompt"`
	OriginalURL string `json:"original_url"`
	MediaID     string `json:"media_id"`
	WechatURL   string `json:"wechat_url"`
	Width       int    `json:"width"`
	Height      int    `json:"height"`
}

// GenerateAndUpload AI 生成图片并上传
func (p *Processor) GenerateAndUpload(prompt string) (*GenerateAndUploadResult, error) {
	p.log.Info("generating image via AI", zap.String("prompt", prompt))

	// 验证配置
	if err := p.cfg.ValidateForImageGeneration(); err != nil {
		return nil, err
	}

	// 检查 provider 是否可用
	if p.provider == nil {
		return nil, fmt.Errorf("图片生成服务未配置，请检查配置文件中的 api.image_provider 和 api.image_key")
	}

	// 调用图片生成 API
	ctx := context.Background()
	result, err := p.provider.Generate(ctx, prompt)
	if err != nil {
		return nil, fmt.Errorf("generate image: %w", err)
	}
	p.log.Info("image generated",
		zap.String("url", result.URL),
		zap.String("provider", result.Model),
		zap.String("size", result.Size))

	// 下载生成的图片
	tmpPath, err := wechat.DownloadFile(result.URL)
	if err != nil {
		return nil, fmt.Errorf("download generated image: %w", err)
	}
	defer os.Remove(tmpPath)

	// 压缩（如果需要）
	processedPath := tmpPath
	if p.cfg.CompressImages {
		compressedPath, compressed, err := p.compressor.CompressImage(tmpPath)
		if err != nil {
			p.log.Warn("compress failed, using original", zap.Error(err))
		} else if compressed {
			processedPath = compressedPath
			defer os.Remove(compressedPath)
			p.log.Info("using compressed image", zap.String("path", processedPath))
		}
	}

	// 上传到微信
	uploadResult, err := p.ws.UploadMaterialWithRetry(processedPath, 3)
	if err != nil {
		return nil, err
	}

	return &GenerateAndUploadResult{
		Prompt:      prompt,
		OriginalURL: result.URL,
		MediaID:     uploadResult.MediaID,
		WechatURL:   uploadResult.WechatURL,
	}, nil
}

// GenerateAndUploadWithSize AI 生成指定尺寸的图片并上传
func (p *Processor) GenerateAndUploadWithSize(prompt string, size string) (*GenerateAndUploadResult, error) {
	p.log.Info("generating image via AI with size",
		zap.String("prompt", prompt),
		zap.String("size", size))

	// 验证配置
	if err := p.cfg.ValidateForImageGeneration(); err != nil {
		return nil, err
	}

	// 检查 provider 是否可用
	if p.provider == nil {
		return nil, fmt.Errorf("图片生成服务未配置，请检查配置文件中的 api.image_provider 和 api.image_key")
	}

	// 创建一个临时配置副本，覆盖尺寸
	originalSize := p.cfg.ImageSize
	p.cfg.ImageSize = size
	defer func() { p.cfg.ImageSize = originalSize }()

	// 重新创建 provider 以使用新尺寸
	newProvider, err := NewProvider(p.cfg)
	if err != nil {
		return nil, fmt.Errorf("create provider with size: %w", err)
	}

	// 调用图片生成 API
	ctx := context.Background()
	result, err := newProvider.Generate(ctx, prompt)
	if err != nil {
		return nil, fmt.Errorf("generate image: %w", err)
	}
	p.log.Info("image generated",
		zap.String("url", result.URL),
		zap.String("provider", result.Model),
		zap.String("size", result.Size))

	// 下载生成的图片
	tmpPath, err := wechat.DownloadFile(result.URL)
	if err != nil {
		return nil, fmt.Errorf("download generated image: %w", err)
	}
	defer os.Remove(tmpPath)

	// 上传到微信
	uploadResult, err := p.ws.UploadMaterialWithRetry(tmpPath, 3)
	if err != nil {
		return nil, err
	}

	return &GenerateAndUploadResult{
		Prompt:      prompt,
		OriginalURL: result.URL,
		MediaID:     uploadResult.MediaID,
		WechatURL:   uploadResult.WechatURL,
	}, nil
}

// GetImageInfo 获取图片信息
func (p *Processor) GetImageInfo(filePath string) (*ImageInfo, error) {
	return GetImageInfo(filePath)
}

// CompressImage 压缩图片（公开方法）
func (p *Processor) CompressImage(filePath string) (string, bool, error) {
	return p.compressor.CompressImage(filePath)
}

// SetCompressQuality 设置压缩质量
func (p *Processor) SetCompressQuality(quality int) {
	p.compressor.SetQuality(quality)
}
