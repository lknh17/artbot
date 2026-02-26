package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/geekjourneyx/md2wechat-skill/internal/draft"
	"github.com/spf13/cobra"
)

var (
	imagePostTitle       string
	imagePostContent     string
	imagePostImages      string
	imagePostFromMD      string
	imagePostOpenComment bool
	imagePostFansOnly    bool
	imagePostDryRun      bool
	imagePostOutput      string
)

var createImagePostCmd = &cobra.Command{
	Use:   "create_image_post",
	Short: "Create WeChat image post (小绿书/newspic)",
	Long: `Create a WeChat Official Account image post (小绿书/图片消息).

This command allows you to create image-only posts (newspic type) with up to 20 images.

Examples:
  # Create with comma-separated images
  md2wechat create_image_post -t "Weekend Trip" --images photo1.jpg,photo2.jpg,photo3.jpg

  # Extract images from Markdown file
  md2wechat create_image_post -t "Travel Diary" -m article.md

  # With description and comment settings
  md2wechat create_image_post -t "Food Blog" -c "Today's lunch" --images food.jpg --open-comment

  # Read description from stdin
  echo "Daily check-in" | md2wechat create_image_post -t "Daily" --images pic.jpg

  # Preview mode (dry-run)
  md2wechat create_image_post -t "Test" --images a.jpg,b.jpg --dry-run`,
	PreRunE: func(cmd *cobra.Command, args []string) error {
		return initConfig()
	},
	Run: func(cmd *cobra.Command, args []string) {
		// 构造请求
		req := &draft.ImagePostRequest{
			Title:       imagePostTitle,
			Content:     imagePostContent,
			OpenComment: imagePostOpenComment,
			FansOnly:    imagePostFansOnly,
		}

		// 处理图片列表
		if imagePostImages != "" {
			for _, img := range strings.Split(imagePostImages, ",") {
				img = strings.TrimSpace(img)
				if img != "" {
					req.Images = append(req.Images, img)
				}
			}
		}

		// 从 Markdown 提取图片
		if imagePostFromMD != "" {
			req.FromMarkdown = imagePostFromMD
		}

		// 从 stdin 读取描述内容
		if imagePostContent == "" && !isTerminal() {
			scanner := bufio.NewScanner(os.Stdin)
			var lines []string
			for scanner.Scan() {
				lines = append(lines, scanner.Text())
			}
			if len(lines) > 0 {
				req.Content = strings.Join(lines, "\n")
			}
		}

		// 验证
		if req.Title == "" {
			responseError(fmt.Errorf("--title is required"))
			return
		}

		if len(req.Images) == 0 && req.FromMarkdown == "" {
			responseError(fmt.Errorf("--images or --from-markdown is required"))
			return
		}

		svc := draft.NewService(cfg, log)

		// Dry-run 模式
		if imagePostDryRun {
			preview, err := svc.GetImagePostPreview(req)
			if err != nil {
				responseError(err)
				return
			}

			// 保存到文件
			if imagePostOutput != "" {
				data, _ := json.MarshalIndent(preview, "", "  ")
				if err := os.WriteFile(imagePostOutput, data, 0644); err != nil {
					responseError(err)
					return
				}
			}

			responseSuccess(map[string]any{
				"mode":    "dry-run",
				"preview": preview,
			})
			return
		}

		// 创建小绿书
		result, err := svc.CreateImagePost(req)
		if err != nil {
			responseError(err)
			return
		}

		// 保存结果到文件
		if imagePostOutput != "" {
			data, _ := json.MarshalIndent(result, "", "  ")
			if err := os.WriteFile(imagePostOutput, data, 0644); err != nil {
				responseError(err)
				return
			}
		}

		responseSuccess(result)
	},
}

// isTerminal 检查 stdin 是否是终端
func isTerminal() bool {
	fi, err := os.Stdin.Stat()
	if err != nil {
		return true
	}
	return fi.Mode()&os.ModeCharDevice != 0
}

func init() {
	createImagePostCmd.Flags().StringVarP(&imagePostTitle, "title", "t", "", "Post title (required)")
	createImagePostCmd.Flags().StringVarP(&imagePostContent, "content", "c", "", "Post description text")
	createImagePostCmd.Flags().StringVar(&imagePostImages, "images", "", "Image paths, comma-separated")
	createImagePostCmd.Flags().StringVarP(&imagePostFromMD, "from-markdown", "m", "", "Extract images from Markdown file")
	createImagePostCmd.Flags().BoolVar(&imagePostOpenComment, "open-comment", false, "Enable comments")
	createImagePostCmd.Flags().BoolVar(&imagePostFansOnly, "fans-only", false, "Only fans can comment")
	createImagePostCmd.Flags().BoolVar(&imagePostDryRun, "dry-run", false, "Preview mode without creating draft")
	createImagePostCmd.Flags().StringVarP(&imagePostOutput, "output", "o", "", "Save result to JSON file")
}
