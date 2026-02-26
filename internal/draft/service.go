package draft

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/geekjourneyx/md2wechat-skill/internal/config"
	"github.com/geekjourneyx/md2wechat-skill/internal/wechat"
	"github.com/silenceper/wechat/v2/officialaccount/draft"
	"go.uber.org/zap"
)

// Service 草稿服务
type Service struct {
	cfg *config.Config
	log *zap.Logger
	ws  *wechat.Service
}

// NewService 创建草稿服务
func NewService(cfg *config.Config, log *zap.Logger) *Service {
	return &Service{
		cfg: cfg,
		log: log,
		ws:  wechat.NewService(cfg, log),
	}
}

// ArticleType 文章类型
type ArticleType string

const (
	ArticleTypeNews    ArticleType = "news"    // 图文消息（默认）
	ArticleTypeNewspic ArticleType = "newspic" // 小绿书/图片消息
)

// ImageItem 图片项（小绿书专用）
type ImageItem struct {
	ImageMediaID string `json:"image_media_id"`
}

// ImageInfo 图片信息（小绿书专用）
type ImageInfo struct {
	ImageList []ImageItem `json:"image_list"`
}

// DraftRequest 草稿请求
type DraftRequest struct {
	Articles []Article `json:"articles"`
}

// Article 文章
type Article struct {
	Title            string `json:"title"`
	Author           string `json:"author,omitempty"`
	Digest           string `json:"digest,omitempty"`
	Content          string `json:"content"`
	ContentSourceURL string `json:"content_source_url,omitempty"`
	ThumbMediaID     string `json:"thumb_media_id,omitempty"`
	ShowCoverPic     int    `json:"show_cover_pic,omitempty"`

	// 小绿书/图片消息专用字段
	ArticleType        ArticleType `json:"article_type,omitempty"`
	NeedOpenComment    int         `json:"need_open_comment,omitempty"`
	OnlyFansCanComment int         `json:"only_fans_can_comment,omitempty"`
	ImageInfo          *ImageInfo  `json:"image_info,omitempty"`
}

// ImagePostRequest 创建小绿书请求
type ImagePostRequest struct {
	Title        string   // 标题（必需）
	Content      string   // 纯文本描述
	Images       []string // 图片路径列表
	OpenComment  bool     // 开启评论
	FansOnly     bool     // 仅粉丝评论
	FromMarkdown string   // 从 MD 文件提取图片
}

// ImagePostResult 创建结果
type ImagePostResult struct {
	MediaID     string   `json:"media_id"`
	DraftURL    string   `json:"draft_url"`
	ImageCount  int      `json:"image_count"`
	UploadedIDs []string `json:"uploaded_ids"`
}

// DraftResult 草稿结果
type DraftResult struct {
	MediaID  string `json:"media_id"`
	DraftURL string `json:"draft_url,omitempty"`
}

// CreateDraftFromFile 从 JSON 文件创建草稿
func (s *Service) CreateDraftFromFile(jsonFile string) (*DraftResult, error) {
	s.log.Info("creating draft from file", zap.String("file", jsonFile))

	// 读取 JSON 文件
	data, err := os.ReadFile(jsonFile)
	if err != nil {
		return nil, fmt.Errorf("read file: %w", err)
	}

	// 解析请求
	var req DraftRequest
	if err := json.Unmarshal(data, &req); err != nil {
		return nil, fmt.Errorf("parse json: %w", err)
	}

	// 验证
	if len(req.Articles) == 0 {
		return nil, fmt.Errorf("no articles in request")
	}

	// 转换为 SDK 格式
	var articles []*draft.Article
	for i, a := range req.Articles {
		if a.Title == "" {
			return nil, fmt.Errorf("article %d: title is required", i)
		}
		if a.Content == "" {
			return nil, fmt.Errorf("article %d: content is required", i)
		}

		article := &draft.Article{
			Title:   a.Title,
			Content: a.Content,
			Digest:  a.Digest,
			Author:  a.Author,
		}

		if a.ThumbMediaID != "" {
			article.ThumbMediaID = a.ThumbMediaID
			article.ShowCoverPic = uint(a.ShowCoverPic)
		}

		if a.ContentSourceURL != "" {
			article.ContentSourceURL = a.ContentSourceURL
		}

		articles = append(articles, article)
	}

	// 调用微信 API
	result, err := s.ws.CreateDraft(articles)
	if err != nil {
		return nil, err
	}

	return &DraftResult{
		MediaID:  result.MediaID,
		DraftURL: result.DraftURL,
	}, nil
}

// CreateDraft 创建草稿
func (s *Service) CreateDraft(articles []Article) (*DraftResult, error) {
	// 转换为 SDK 格式
	var draftArticles []*draft.Article
	for _, a := range articles {
		article := &draft.Article{
			Title:   a.Title,
			Content: a.Content,
			Digest:  a.Digest,
			Author:  a.Author,
		}

		if a.ThumbMediaID != "" {
			article.ThumbMediaID = a.ThumbMediaID
			article.ShowCoverPic = uint(a.ShowCoverPic)
		}

		if a.ContentSourceURL != "" {
			article.ContentSourceURL = a.ContentSourceURL
		}

		draftArticles = append(draftArticles, article)
	}

	// 调用微信 API
	result, err := s.ws.CreateDraft(draftArticles)
	if err != nil {
		return nil, err
	}

	return &DraftResult{
		MediaID:  result.MediaID,
		DraftURL: result.DraftURL,
	}, nil
}

// GenerateDigestFromContent 从内容生成摘要
func GenerateDigestFromContent(content string, maxLen int) string {
	if maxLen == 0 {
		maxLen = 120
	}

	// 简化实现：去除 HTML 标签后截取
	// 实际应该使用 HTML 解析器

	// 移除 HTML 标签的简单方法
	content = stripHTML(content)

	// 截取
	if len(content) > maxLen {
		content = content[:maxLen] + "..."
	}

	return content
}

// stripHTML 去除 HTML 标签（简化版）
func stripHTML(html string) string {
	// 简化实现：移除常见标签
	// 实际应该使用 proper HTML 解析器
	result := html
	for _, tag := range []string{"</p>", "<br/>", "<br>", "</div>", "</h1>", "</h2>", "</h3>"} {
		result = strings.ReplaceAll(result, tag, "\n")
	}

	// 移除所有标签
	inTag := false
	var clean strings.Builder
	for _, r := range result {
		if r == '<' {
			inTag = true
		} else if r == '>' {
			inTag = false
		} else if !inTag {
			clean.WriteRune(r)
		}
	}

	return clean.String()
}

// CreateImagePost 创建小绿书（图片消息）
func (s *Service) CreateImagePost(req *ImagePostRequest) (*ImagePostResult, error) {
	s.log.Info("creating image post", zap.String("title", req.Title))

	// 验证标题
	if req.Title == "" {
		return nil, fmt.Errorf("title is required")
	}

	// 获取图片列表
	images := req.Images
	if req.FromMarkdown != "" {
		extracted := extractImagesFromMarkdown(req.FromMarkdown)
		images = append(images, extracted...)
	}

	if len(images) == 0 {
		return nil, fmt.Errorf("no images provided")
	}

	// 微信限制最多 20 张图片
	if len(images) > 20 {
		return nil, fmt.Errorf("too many images: %d (max 20)", len(images))
	}

	// 上传图片获取 media_id
	var imageList []wechat.NewspicImageItem
	var uploadedIDs []string

	for i, imgPath := range images {
		s.log.Info("uploading image",
			zap.Int("index", i+1),
			zap.Int("total", len(images)),
			zap.String("path", imgPath))

		result, err := s.ws.UploadMaterialWithRetry(imgPath, 3)
		if err != nil {
			return nil, fmt.Errorf("upload image %d (%s): %w", i+1, imgPath, err)
		}

		imageList = append(imageList, wechat.NewspicImageItem{
			ImageMediaID: result.MediaID,
		})
		uploadedIDs = append(uploadedIDs, result.MediaID)
	}

	// 构造文章
	article := wechat.NewspicArticle{
		Title:       req.Title,
		Content:     req.Content,
		ArticleType: "newspic",
		ImageInfo: wechat.NewspicImageInfo{
			ImageList: imageList,
		},
	}

	// 评论设置
	if req.OpenComment {
		article.NeedOpenComment = 1
		if req.FansOnly {
			article.OnlyFansCanComment = 1
		}
	}

	// 调用微信 API 创建草稿
	result, err := s.ws.CreateNewspicDraft([]wechat.NewspicArticle{article})
	if err != nil {
		return nil, fmt.Errorf("create draft: %w", err)
	}

	return &ImagePostResult{
		MediaID:     result.MediaID,
		DraftURL:    result.DraftURL,
		ImageCount:  len(images),
		UploadedIDs: uploadedIDs,
	}, nil
}

// extractImagesFromMarkdown 从 Markdown 文件提取图片路径
func extractImagesFromMarkdown(mdFile string) []string {
	content, err := os.ReadFile(mdFile)
	if err != nil {
		return nil
	}

	// 匹配 Markdown 图片语法: ![alt](path) 或 ![alt](path "title")
	re := regexp.MustCompile(`!\[[^\]]*\]\(([^)"\s]+)(?:\s+"[^"]*")?\)`)
	matches := re.FindAllStringSubmatch(string(content), -1)

	// 获取 Markdown 文件所在目录
	mdDir := filepath.Dir(mdFile)

	var images []string
	for _, match := range matches {
		if len(match) > 1 {
			imgPath := match[1]
			// 跳过网络图片
			if strings.HasPrefix(imgPath, "http://") || strings.HasPrefix(imgPath, "https://") {
				continue
			}
			// 转换相对路径为绝对路径
			if !filepath.IsAbs(imgPath) {
				imgPath = filepath.Join(mdDir, imgPath)
			}
			images = append(images, imgPath)
		}
	}

	return images
}

// GetImagePostPreview 获取小绿书预览信息（dry-run 用）
func (s *Service) GetImagePostPreview(req *ImagePostRequest) (map[string]any, error) {
	// 获取图片列表
	images := req.Images
	if req.FromMarkdown != "" {
		extracted := extractImagesFromMarkdown(req.FromMarkdown)
		images = append(images, extracted...)
	}

	if len(images) == 0 {
		return nil, fmt.Errorf("no images provided")
	}

	if len(images) > 20 {
		return nil, fmt.Errorf("too many images: %d (max 20)", len(images))
	}

	// 检查图片文件是否存在
	var imageDetails []map[string]any
	for _, imgPath := range images {
		info, err := os.Stat(imgPath)
		detail := map[string]any{
			"path":   imgPath,
			"exists": err == nil,
		}
		if err == nil {
			detail["size"] = info.Size()
		}
		imageDetails = append(imageDetails, detail)
	}

	return map[string]any{
		"title":        req.Title,
		"content":      req.Content,
		"image_count":  len(images),
		"images":       imageDetails,
		"open_comment": req.OpenComment,
		"fans_only":    req.FansOnly,
	}, nil
}
