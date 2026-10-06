# 나만의 피지컬 AI 제품 만들기

이 폴더는 과제 제출용 작업 폴더입니다.
나만의 피지컬 AI 제품을 기획하고, 그 제품을 소개하는 홈페이지를 만들어 GitHub Pages로 배포합니다.

## 폴더 구성

```
physicalAI/
├── README.md          ← 지금 보고 있는 안내 문서
├── index.html         ← 제품 소개 홈페이지 (GitHub Pages 시작 파일)
├── images/            ← 홈페이지에 쓸 이미지 (제품 사진, 스케치 등)
├── PRD/
│   └── PRD.md         ← 제품 요구사항 문서 (무엇을, 왜, 어떻게 만들지)
└── report/
    └── report.md      ← 과제 보고서 (과정, 회고, 배운 점)
```

## GitHub Pages 배포 방법

cd 
git init
git add .
git commit -m "처음 커밋"

git remote remove origin

git remote add origin https://github.com/maraoj1004-collab/physical-ai


git branch -M main
git push -u origin main --force


---

git init
git branch -M main
git remote remove origin
git remote add origin 
git add .
git commit -m "수정 내용에 대한 설명"
git push -u origin main --force
